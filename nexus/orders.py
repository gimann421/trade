"""Simulated/paper order lifecycle: pre-registered decisions, gated proposals, validated state transitions."""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import yaml

from . import permissions, risk_gate
from .accounting import D, ZERO, state_from_entries
from .domain.enums import ALLOWED_ORDER_TRANSITIONS, EventType, LedgerKind, OrderState
from .errors import NexusError
from .ingestion import DecisionDataGate, bars_known_at
from .store import Store
from .timeutil import require_aware, to_iso

SIM_CONFIG = Path(__file__).parent / "config" / "simulation.yaml"


def load_sim_config(path: Path = SIM_CONFIG) -> dict:
    cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    for k in ("slippage_bps", "half_spread_bps", "participation_cap", "fill_model"):
        if k not in cfg:
            raise NexusError(f"simulation.yaml missing {k}")
    return cfg


@dataclass(frozen=True)
class OrderRequest:
    account_id: str
    instrument_id: str
    side: str                     # BUY | SELL
    quantity: str
    strategy_id: str
    strategy_version: str
    rationale: str
    order_type: str = "MARKET"
    limit_price: str | None = None
    mode: str = "simulated"       # 'paper_broker' = also routed to the Alpaca paper API (never live)
    client_key: str | None = None  # idempotency key: re-proposing the same decision returns the original order


def current_state(store: Store, order_id: str) -> OrderState:
    r = store.conn.execute("SELECT to_state FROM order_transitions WHERE order_id=? ORDER BY seq DESC LIMIT 1", (order_id,)).fetchone()
    if r is None:
        raise NexusError(f"unknown order {order_id}")
    return OrderState(r["to_state"])


def transition(store: Store, order_id: str, to: OrderState, at: datetime, detail: dict | None = None) -> None:
    cur = current_state(store, order_id)
    if to not in ALLOWED_ORDER_TRANSITIONS[cur]:
        raise NexusError(f"illegal order transition {cur.value} -> {to.value}")
    store.conn.execute("INSERT INTO order_transitions (order_id, from_state, to_state, at, detail_json) VALUES (?,?,?,?,?)",
                       (order_id, cur.value, to.value, to_iso(require_aware(at, "at")), json.dumps(detail or {}, sort_keys=True)))
    store.events.append(EventType.ORDER_STATE_CHANGED, "orders", "system", {"order_id": order_id, "from": cur.value, "to": to.value},
                        occurred_at=at)


def propose_order(store: Store, req: OrderRequest, now: datetime, fallback_marks: dict[str, Decimal] | None = None) -> str:
    """Decision -> data gate -> risk gate -> pre-registered decision event -> immutable order + PROPOSED/REJECTED state.

    The decision event is stamped with ``now`` BEFORE any later market outcome can exist; the order row carries its id.
    """
    permissions.require(permissions.Capability.SIMULATE_ORDER, store.config.permissions.allowed)
    permissions.require(permissions.Capability.RECORD_HYPOTHETICAL_TRADE, store.config.permissions.allowed)
    if req.mode == "paper_broker":
        permissions.require(permissions.Capability.PAPER_BROKER_ORDER, store.config.permissions.allowed)
    elif req.mode != "simulated":
        raise NexusError("mode must be 'simulated' or 'paper_broker'")
    if req.side not in ("BUY", "SELL") or req.order_type not in ("MARKET", "LIMIT"):
        raise NexusError("bad side or order type")
    if req.order_type == "LIMIT" and req.limit_price is None:
        raise NexusError("limit orders need a limit_price")
    if not req.rationale.strip():
        raise NexusError("a rationale is required")
    qty = D(req.quantity)
    if req.client_key is not None:
        dup = store.conn.execute("SELECT order_id, instrument_id, side, quantity, strategy_id FROM orders WHERE account_id=? AND client_key=?",
                                 (req.account_id, req.client_key)).fetchone()
        if dup is not None:
            if (dup["instrument_id"], dup["side"], Decimal(dup["quantity"]), dup["strategy_id"]) != (req.instrument_id, req.side, qty, req.strategy_id):
                raise NexusError("client_key reused with a different order")
            return dup["order_id"]
    kind = store.conn.execute("SELECT kind FROM ledger_accounts WHERE account_id=?", (req.account_id,)).fetchone()
    if kind is None:
        raise NexusError("unknown account")
    kind = LedgerKind(kind["kind"])
    if kind is LedgerKind.ACTUAL:
        raise permissions.LaunchBoundaryViolation("orders can never target the ACTUAL ledger")
    if req.mode == "paper_broker" and kind is not LedgerKind.PAPER_SLEEVE:
        raise NexusError("only PAPER_SLEEVE accounts may route to the paper broker")
    inst = store.get_instrument(req.instrument_id)
    if inst is None:
        raise NexusError(f"unregistered instrument {req.instrument_id}")
    # fail closed on data and system state (raises on stale/missing data, halt, broken audit chain)
    DecisionDataGate(store).require(req.instrument_id, now)
    bars = bars_known_at(store, req.instrument_id, now)
    snap_ids = [r["snapshot_id"] for r in store.conn.execute(
        "SELECT DISTINCT snapshot_id FROM bars WHERE instrument_id=? AND session_date=?", (req.instrument_id, bars[-1].session_date))]
    ref_price = D(str(bars[-1].close)) if req.order_type == "MARKET" else D(req.limit_price)
    state = state_from_entries(store, req.account_id, now)
    marks, fb_used = {}, {}
    for iid in state.positions:
        b = bars_known_at(store, iid, now)
        if b:
            marks[iid] = D(str(b[-1].close))
        elif fallback_marks and iid in fallback_marks:       # explicit, recorded, owner-supplied mark for a held name the feed lacks
            marks[iid] = D(str(fallback_marks[iid]))
            fb_used[iid] = str(marks[iid])
    risk = risk_gate.evaluate(store.config.risk_limits, kind, inst, req.side, qty, ref_price, state, marks)
    cfg = load_sim_config()
    ev = store.events.append(EventType.DECISION_RECORDED, "orders", req.strategy_id,
                             {"strategy": req.strategy_id, "version": req.strategy_version, "account_id": req.account_id,
                              "instrument_id": req.instrument_id, "side": req.side, "quantity": str(qty),
                              "order_type": req.order_type, "limit_price": req.limit_price, "rationale": req.rationale,
                              "snapshots": snap_ids, "risk_approved": risk.approved, "risk_reasons": risk.reasons,
                              "fill_model": cfg["fill_model"], "fallback_marks_used": fb_used}, occurred_at=now)
    order_id = f"ord-{uuid.uuid4().hex[:16]}"
    store.conn.execute("INSERT INTO orders (order_id, account_id, instrument_id, side, quantity, order_type, limit_price, time_in_force, strategy_id, strategy_version, decision_ts, decision_event_id, data_snapshot_ids, rationale, fill_model, risk_json, mode, client_key) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                       (order_id, req.account_id, req.instrument_id, req.side, str(qty), req.order_type, req.limit_price, "DAY",
                        req.strategy_id, req.strategy_version, to_iso(now), ev.event_id, json.dumps(snap_ids), req.rationale,
                        cfg["fill_model"], json.dumps({"approved": risk.approved, "reasons": risk.reasons}), req.mode, req.client_key))
    store.conn.execute("INSERT INTO order_transitions (order_id, from_state, to_state, at, detail_json) VALUES (?,?,?,?,?)",
                       (order_id, None, OrderState.PROPOSED.value, to_iso(now), "{}"))
    if not risk.approved:
        transition(store, order_id, OrderState.REJECTED, now, {"reasons": risk.reasons})
    else:
        transition(store, order_id, OrderState.ACCEPTED_BY_SIMULATOR, now, {})
    return order_id
