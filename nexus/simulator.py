"""Conservative fill simulation with no look-ahead.

A market order decided at time T fills at the OPEN of the first session whose open is strictly after T,
adjusted adversely for slippage and half-spread, capped at a fraction of that bar's volume. A limit order
fills only if that session's range reaches the limit (at the worse of open and limit) and otherwise expires
at the end of the session (DAY). Fills post a TRADE to the sleeve's ledger.
"""
from __future__ import annotations

import json
from datetime import date, datetime
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal

from .accounting import D, ZERO, record_entry
from .domain.enums import OrderState
from .errors import NexusError
from .ingestion import bars_known_at, calendar_for
from .orders import current_state, load_sim_config, transition
from .store import Store
from .timeutil import require_aware

CENT = Decimal("0.0001")


def _filled_qty(store: Store, order_id: str) -> Decimal:
    t = ZERO
    for r in store.conn.execute("SELECT detail_json FROM order_transitions WHERE order_id=? AND to_state IN (?,?)",
                                (order_id, OrderState.PARTIALLY_FILLED.value, OrderState.FILLED.value)):
        t += Decimal(json.loads(r["detail_json"]).get("fill_qty", "0"))
    return t


def try_fill(store: Store, order_id: str, now: datetime) -> OrderState:
    """Advance one order using only bars known at ``now``. Idempotent per session."""
    now = require_aware(now, "now")
    o = store.conn.execute("SELECT * FROM orders WHERE order_id=?", (order_id,)).fetchone()
    state = current_state(store, order_id)
    if state not in (OrderState.ACCEPTED_BY_SIMULATOR, OrderState.PARTIALLY_FILLED):
        return state
    if o["mode"] != "simulated":
        raise NexusError("paper-broker orders are filled by the broker, not the simulator")
    store.controls.assert_can_create_simulated_orders()
    cfg = load_sim_config()
    cal = calendar_for(store, o["instrument_id"])
    decision_ts = datetime.fromisoformat(o["decision_ts"])
    target = None
    for b in bars_known_at(store, o["instrument_id"], now):
        d = date.fromisoformat(b.session_date)
        if cal.session_open(d) > decision_ts:
            target = b
            break
    if target is None:
        return state                                        # no eligible bar known yet: nothing to do (no peeking)
    d = date.fromisoformat(target.session_date)
    close_ts = cal.session_close(d)
    if close_ts > now:
        return state                                        # session not finished: its bar is not final
    qty_total, filled = D(o["quantity"]), _filled_qty(store, order_id)
    remaining = qty_total - filled
    if remaining <= 0:
        return state
    slip = (D(cfg["slippage_bps"]) + D(cfg["half_spread_bps"])) / Decimal(10000)
    open_, high, low = D(str(target.open)), D(str(target.high)), D(str(target.low))
    buy = o["side"] == "BUY"
    if o["order_type"] == "MARKET":
        px = open_ * (1 + slip) if buy else open_ * (1 - slip)
    else:
        lim = D(o["limit_price"])
        crossed = low <= lim if buy else high >= lim
        if not crossed:
            transition(store, order_id, OrderState.EXPIRED, close_ts, {"reason": "limit not reached in session"})
            return OrderState.EXPIRED
        px = min(open_, lim) if buy else max(open_, lim)
        px = px * (1 + slip) if buy else px * (1 - slip)
        px = min(px, lim) if buy else max(px, lim)          # never worse than the limit
    px = px.quantize(CENT, rounding=ROUND_HALF_UP)
    cap = (D(str(target.volume)) * D(str(cfg["participation_cap"]))).quantize(Decimal("0.0001"), rounding=ROUND_DOWN)
    qty = min(remaining, cap)
    if qty <= 0:
        transition(store, order_id, OrderState.EXPIRED, close_ts, {"reason": "no liquidity under participation cap"})
        return OrderState.EXPIRED
    fee = D(cfg.get("fee_per_order", "0"))
    signed = qty if buy else -qty
    fill_ts = cal.session_open(d)
    try:
        record_entry(store, o["account_id"], "TRADE", fill_ts, instrument_id=o["instrument_id"], qty_delta=str(signed), price=str(px),
                     fee=str(fee), cash_delta=str(-signed * px - fee), ref=order_id, note=f"simulated fill {cfg['fill_model']}",
                     actor="simulator")
    except NexusError as exc:
        if "cash negative" not in str(exc):
            raise
        # earlier fills used the cash this order was approved against: the order dies unfilled, the ledger is never leveraged
        transition(store, order_id, OrderState.EXPIRED, close_ts, {"reason": "insufficient simulated cash at fill; order not filled"})
        return OrderState.EXPIRED
    detail = {"fill_qty": str(qty), "fill_price": str(px), "fee": str(fee), "bar": target.session_date, "model": cfg["fill_model"]}
    if qty < remaining:
        transition(store, order_id, OrderState.PARTIALLY_FILLED, close_ts, detail)
        # DAY order: the unfilled remainder dies with the session (never silently left working)
        transition(store, order_id, OrderState.EXPIRED, close_ts, {"reason": "day order ended with remainder",
                                                                   "unfilled_qty": str(remaining - qty)})
        return OrderState.EXPIRED
    transition(store, order_id, OrderState.FILLED, close_ts, detail)
    return OrderState.FILLED
