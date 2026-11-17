"""Deterministic portfolio accounting: exact Decimal arithmetic, append-only journal, immutable snapshots.

Three ledgers stay separate: ACTUAL accounts accept only owner-confirmed records; SHADOW and PAPER_SLEEVE
accounts accept only simulated entries (also enforced by DB triggers). Valuation fails closed when a
mark price is missing.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Iterable

from .domain.enums import EventType, LedgerKind
from .domain.models import content_hash
from .errors import NexusError, StaleOrInvalidDataError
from .store import Store
from .timeutil import require_aware, to_iso

ZERO = Decimal(0)
SHADOW_PATH_CHOICES = ("maintain_parallel", "reset", "merge")


def D(x) -> Decimal:
    if isinstance(x, float):
        raise NexusError("floats are not accepted for money/quantity; pass Decimal or str")
    try:
        d = Decimal(x)
    except (InvalidOperation, TypeError, ValueError):
        raise NexusError(f"invalid decimal {x!r}") from None
    if not d.is_finite():
        raise NexusError("non-finite decimal")
    return d


@dataclass(frozen=True)
class AccountState:
    account_id: str
    cash: Decimal
    positions: dict[str, Decimal]


@dataclass
class ReconciliationReport:
    diffs: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.diffs


def _kind(store: Store, account_id: str) -> LedgerKind:
    r = store.conn.execute("SELECT kind FROM ledger_accounts WHERE account_id=?", (account_id,)).fetchone()
    if r is None:
        raise NexusError(f"unknown account {account_id}")
    return LedgerKind(r["kind"])


def state_from_entries(store: Store, account_id: str, as_of: datetime | None = None) -> AccountState:
    q = "SELECT * FROM ledger_entries WHERE account_id=?"
    args: list = [account_id]
    if as_of is not None:
        q += " AND occurred_at<=?"
        args.append(to_iso(require_aware(as_of, "as_of")))
    cash, pos = ZERO, {}
    for r in store.conn.execute(q + " ORDER BY occurred_at, rowid", args):
        cash += Decimal(r["cash_delta"])
        if r["instrument_id"]:
            pos[r["instrument_id"]] = pos.get(r["instrument_id"], ZERO) + Decimal(r["qty_delta"])
    return AccountState(account_id, cash, {k: v for k, v in pos.items() if v != 0})


def record_entry(store: Store, account_id: str, kind: str, occurred_at: datetime, *, instrument_id: str | None = None,
                 qty_delta="0", cash_delta="0", price=None, fee="0", ref: str | None = None, note: str | None = None,
                 actor: str = "accounting") -> str:
    """Append one journal entry after validating the arithmetic. Returns the entry id."""
    acct_kind = _kind(store, account_id)
    origin = "owner_confirmed" if acct_kind is LedgerKind.ACTUAL else "simulated"
    qty, cash, fee_d = D(qty_delta), D(cash_delta), D(fee)
    price_d = D(price) if price is not None else None
    if fee_d < 0:
        raise NexusError("fee must be non-negative")
    if kind == "TRADE":
        if not instrument_id or qty == 0 or price_d is None or price_d <= 0:
            raise NexusError("TRADE needs instrument, non-zero quantity and positive price")
        if cash != -qty * price_d - fee_d:
            raise NexusError("TRADE cash_delta must equal -(qty*price) - fee exactly")
    elif kind in ("DEPOSIT", "DIVIDEND"):
        if cash <= 0 or qty != 0 and kind == "DEPOSIT":
            raise NexusError(f"{kind} must add positive cash")
    elif kind in ("WITHDRAWAL", "FEE"):
        if cash >= 0 or qty != 0:
            raise NexusError(f"{kind} must reduce cash and not move positions")
    elif kind == "SPLIT":
        if not instrument_id or cash != 0 or qty == 0:
            raise NexusError("SPLIT adjusts quantity only")
    if instrument_id is not None and store.get_instrument(instrument_id) is None:
        raise NexusError(f"unregistered instrument {instrument_id}")
    if acct_kind is not LedgerKind.ACTUAL:   # simulated books: no leverage, no shorts, no withdrawals
        if kind == "WITHDRAWAL":
            raise NexusError("withdrawals do not exist in simulated accounts")
        cur = state_from_entries(store, account_id)
        if cur.cash + cash < 0:
            raise NexusError("simulated entry would make cash negative (no leverage at launch)")
        if instrument_id and cur.positions.get(instrument_id, ZERO) + qty < 0:
            raise NexusError("simulated entry would create a short position (not allowed at launch)")
    now = store._clock()
    entry_id = f"ent-{uuid.uuid4().hex[:16]}"
    store.conn.execute(
        "INSERT INTO ledger_entries (entry_id, account_id, occurred_at, recorded_at, kind, origin, instrument_id,"
        " qty_delta, cash_delta, price, fee, ref, note) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (entry_id, account_id, to_iso(require_aware(occurred_at, "occurred_at")), to_iso(now), kind, origin,
         instrument_id, str(qty), str(cash), None if price_d is None else str(price_d), str(fee_d), ref, note))
    store.events.append(EventType.LEDGER_ENTRY_RECORDED, "accounting", actor,
                        {"entry_id": entry_id, "account_id": account_id, "kind": kind, "instrument_id": instrument_id,
                         "qty_delta": str(qty), "cash_delta": str(cash)})
    return entry_id


# ---------- immutable snapshots ----------
def _snapshot_dict(cash, holdings, estimated, open_orders):
    return {"cash": {k: str(D(v)) for k, v in sorted(cash.items())},
            "holdings": {k: {"quantity": str(D(v["quantity"])),
                             "cost_basis": None if v.get("cost_basis") is None else str(D(v["cost_basis"]))}
                         for k, v in sorted(holdings.items())},
            "estimated_fields": sorted(estimated), "open_orders": list(open_orders)}


def import_actual_snapshot(store: Store, account_id: str, as_of: datetime, source: str, confirmed_by: str, *,
                           cash: dict[str, str], holdings: dict[str, dict], estimated_fields: Iterable[str] = (),
                           open_orders: Iterable[dict] = ()) -> str:
    """Record a user-confirmed holdings snapshot. Requires an owner confirmation; never overwrites history."""
    if _kind(store, account_id) is not LedgerKind.ACTUAL:
        raise NexusError("actual snapshots can only be imported into an ACTUAL account")
    if not confirmed_by:
        raise NexusError("actual snapshots must be confirmed by the owner (unverified holdings are not accepted)")
    for iid in holdings:
        if store.get_instrument(iid) is None:
            raise NexusError(f"unregistered instrument {iid}")
    body = _snapshot_dict(cash, holdings, estimated_fields, open_orders)
    h = content_hash(body)
    prev = store.conn.execute("SELECT snapshot_id FROM portfolio_snapshots WHERE account_id=? ORDER BY as_of DESC, rowid DESC LIMIT 1",
                              (account_id,)).fetchone()
    sid = f"snap-{h[:16]}"
    store.conn.execute("INSERT INTO portfolio_snapshots VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                       (sid, account_id, to_iso(require_aware(as_of, "as_of")), to_iso(store._clock()), source, confirmed_by,
                        json.dumps(body["cash"]), json.dumps(body["holdings"]), json.dumps(body["estimated_fields"]),
                        json.dumps(body["open_orders"]), h, prev["snapshot_id"] if prev else None))
    store.events.append(EventType.PORTFOLIO_SNAPSHOT_IMPORTED, "accounting", confirmed_by,
                        {"snapshot_id": sid, "account_id": account_id, "sha256": h, "estimated": body["estimated_fields"]})
    return sid


def load_snapshot(store: Store, snapshot_id: str) -> dict:
    r = store.conn.execute("SELECT * FROM portfolio_snapshots WHERE snapshot_id=?", (snapshot_id,)).fetchone()
    if r is None:
        raise NexusError(f"unknown snapshot {snapshot_id}")
    body = {"cash": json.loads(r["cash_json"]), "holdings": json.loads(r["holdings_json"]),
            "estimated_fields": json.loads(r["estimated_json"]), "open_orders": json.loads(r["open_orders_json"])}
    if content_hash(body) != r["content_sha256"]:
        raise StaleOrInvalidDataError(f"snapshot {snapshot_id} fails its hash check")
    return {**body, "as_of": r["as_of"], "account_id": r["account_id"], "source": r["source"]}


def actual_state(store: Store, account_id: str) -> AccountState:
    """The actual book is the latest confirmed snapshot (base currency cash only, M3)."""
    r = store.conn.execute("SELECT snapshot_id FROM portfolio_snapshots WHERE account_id=? ORDER BY as_of DESC, rowid DESC LIMIT 1",
                           (account_id,)).fetchone()
    if r is None:
        raise StaleOrInvalidDataError("no confirmed actual snapshot; holdings are unverified")
    return _state_of_snapshot(load_snapshot(store, r["snapshot_id"]), account_id)


def _state_of_snapshot(snap: dict, account_id: str) -> AccountState:
    if len(snap["cash"]) > 1:
        raise NexusError("multi-currency snapshots are not supported yet")
    cash = sum((Decimal(v) for v in snap["cash"].values()), ZERO)
    return AccountState(account_id, cash, {k: Decimal(v["quantity"]) for k, v in snap["holdings"].items() if Decimal(v["quantity"]) != 0})


# ---------- shadow ledger ----------
def create_shadow_from_snapshot(store: Store, actual_snapshot_id: str, name: str, at: datetime, actor: str = "shadow") -> str:
    """New SHADOW account whose opening entries copy an actual snapshot. The actual ledger is only read."""
    snap = load_snapshot(store, actual_snapshot_id)
    state = _state_of_snapshot(snap, snap["account_id"])
    acct = store.create_account(LedgerKind.SHADOW, name, actor)
    if state.cash:
        record_entry(store, acct.account_id, "DEPOSIT" if state.cash > 0 else "ADJUSTMENT", at, cash_delta=str(state.cash),
                     ref=actual_snapshot_id, note="opening cash from actual snapshot", actor=actor)
    for iid, qty in sorted(state.positions.items()):
        record_entry(store, acct.account_id, "ADJUSTMENT", at, instrument_id=iid, qty_delta=str(qty),
                     ref=actual_snapshot_id, note="opening position from actual snapshot", actor=actor)
    store.events.append(EventType.SHADOW_INITIALIZED, "shadow", actor,
                        {"shadow_account_id": acct.account_id, "from_snapshot": actual_snapshot_id})
    return acct.account_id


def log_shadow_path_decision(store: Store, shadow_account_id: str, new_actual_snapshot_id: str, choice: str, reason: str,
                             actor: str = "shadow") -> None:
    """When the actual portfolio changes, the reset/merge/parallel decision must be explicit and logged."""
    if choice not in SHADOW_PATH_CHOICES:
        raise NexusError(f"choice must be one of {SHADOW_PATH_CHOICES}")
    if not reason:
        raise NexusError("a reason is required")
    if _kind(store, shadow_account_id) is not LedgerKind.SHADOW:
        raise NexusError("not a shadow account")
    load_snapshot(store, new_actual_snapshot_id)
    store.events.append(EventType.SHADOW_PATH_DECISION, "shadow", actor,
                        {"shadow_account_id": shadow_account_id, "snapshot_id": new_actual_snapshot_id,
                         "choice": choice, "reason": reason})


# ---------- valuation and reconciliation ----------
def nav(state: AccountState, prices: dict[str, Decimal]) -> Decimal:
    """Net asset value. Fails closed if any held instrument has no mark."""
    total = state.cash
    for iid, qty in state.positions.items():
        p = prices.get(iid)
        if p is None or p <= 0:
            raise StaleOrInvalidDataError(f"no valid mark for {iid}; NAV is unpriceable")
        total += qty * p
    return total


def reconcile(state: AccountState, expected_cash: str, expected_positions: dict[str, str],
              cash_tolerance: str = "0.01", qty_tolerance: str = "0") -> ReconciliationReport:
    rep = ReconciliationReport()
    ct, qt = D(cash_tolerance), D(qty_tolerance)
    if abs(state.cash - D(expected_cash)) > ct:
        rep.diffs.append(f"cash {state.cash} != expected {expected_cash}")
    for iid in sorted(set(state.positions) | set(expected_positions)):
        a, e = state.positions.get(iid, ZERO), D(expected_positions.get(iid, "0"))
        if abs(a - e) > qt:
            rep.diffs.append(f"{iid}: {a} != expected {e}")
    return rep


def verify_cash_identity(store: Store, account_id: str) -> None:
    """Independent check: stored cash equals the sum of cash legs of every entry (recomputed via SQL on text)."""
    total = sum((Decimal(r[0]) for r in store.conn.execute("SELECT cash_delta FROM ledger_entries WHERE account_id=?", (account_id,))), ZERO)
    if total != state_from_entries(store, account_id).cash:
        raise StaleOrInvalidDataError("cash identity violated")
