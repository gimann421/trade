"""Forward-test sleeve for G1 and shadow-portfolio buy ideas. SIMULATED only; nothing here reaches any broker.

* Sleeve: a PAPER_SLEEVE ledger ($100k notional) that follows G1 forward in time. Every decision is stamped before its outcome
  (``propose_order`` -> data gate -> risk gate -> pre-registered DECISION event); fills come from the conservative simulator
  at the next session's open. It is an observation record, not a claim that G1 is validated (see the research results).
* Shadow ideas: small hypothetical buys in the SHADOW copy of the owner's portfolio, funded from its cash, same gates.
"""
from __future__ import annotations

from datetime import datetime
from decimal import ROUND_DOWN, Decimal

from .accounting import ZERO, record_entry, state_from_entries
from .domain.enums import LedgerKind, OrderState
from .errors import NexusError
from .ideas import G1_ID, current_ideas, iid, target_weights
from .ingestion import bars_known_at
from .orders import OrderRequest, current_state, propose_order
from .simulator import try_fill
from .store import Store

SLEEVE_NAME = "G1 forward test"
SLEEVE_CAPITAL = "100000"
MIN_TRADE_USD = Decimal("250")


def _hist(store: Store, symbols: list[str], now: datetime):
    return {iid(s): bars_known_at(store, iid(s), now) for s in symbols if bars_known_at(store, iid(s), now)}


def ensure_sleeve(store: Store, now: datetime) -> str:
    for a in store.list_accounts(LedgerKind.PAPER_SLEEVE):
        if a.name == SLEEVE_NAME:
            return a.account_id
    acct = store.create_account(LedgerKind.PAPER_SLEEVE, SLEEVE_NAME, "sleeve")
    record_entry(store, acct.account_id, "DEPOSIT", now, cash_delta=SLEEVE_CAPITAL, note="notional starting capital (simulated)")
    return acct.account_id


def _marks(store: Store, state, now):
    return {i: Decimal(str(bars_known_at(store, i, now)[-1].close)) for i in state.positions}


def _qty(value: Decimal, price: Decimal) -> Decimal:
    return (value / price).quantize(Decimal("1"), rounding=ROUND_DOWN)


def fill_pending(store: Store, now: datetime) -> int:
    """Advance every simulated order (sleeve and shadow) that a newly final session bar allows. Never touches a broker."""
    n = 0
    for r in store.conn.execute("SELECT order_id FROM orders WHERE mode='simulated'").fetchall():
        if current_state(store, r[0]) in (OrderState.ACCEPTED_BY_SIMULATOR, OrderState.PARTIALLY_FILLED):
            if try_fill(store, r[0], now) is OrderState.FILLED:
                n += 1
    return n


def run_sleeve(store: Store, now: datetime, symbols: list[str]) -> dict:
    """Fill what is fillable, then (first run, or first session of a new month) re-target G1. Idempotent per decision month."""
    acct = ensure_sleeve(store, now)
    filled = fill_pending(store, now)
    hist = _hist(store, symbols, now)
    if not hist:
        raise NexusError("no priced instruments; sleeve cannot decide")
    last_day = max(b[-1].session_date for b in hist.values())
    month = last_day[:7]
    done = store.conn.execute("SELECT 1 FROM orders WHERE account_id=? AND client_key LIKE ? LIMIT 1", (acct, f"g1:{month}:%")).fetchone()
    first_session = all(not any(b.session_date[:7] == month and b.session_date < last_day for b in bs) for bs in hist.values())
    never = store.conn.execute("SELECT 1 FROM orders WHERE account_id=? LIMIT 1", (acct,)).fetchone() is None
    if done or not (first_session or never):
        return {"filled": filled, "decision": "none", "reason": "already decided this month" if done else "not a rebalance day"}
    targets = target_weights(hist)
    state = state_from_entries(store, acct, now)
    marks = _marks(store, state, now)
    px = {i: Decimal(str(bs[-1].close)) for i, bs in hist.items()}
    marks.update({i: px[i] for i in targets})
    total = state.cash + sum((q * marks[i] for i, q in state.positions.items()), ZERO)
    placed, plans = [], []
    for i in sorted(set(targets) | set(state.positions)):
        want = _qty(Decimal(str(targets.get(i, 0.0))) * total, px.get(i, marks.get(i, Decimal(1)))) if i in targets else ZERO
        delta = want - state.positions.get(i, ZERO)
        p = px.get(i) or marks.get(i)
        if p and abs(delta * p) >= MIN_TRADE_USD or (want == 0 and delta < 0):
            plans.append((i, delta))
    for i, delta in sorted(plans, key=lambda t: t[1]):             # sells first so cash exists for buys
        side = "BUY" if delta > 0 else "SELL"
        oid = propose_order(store, OrderRequest(acct, i, side, str(abs(delta)), G1_ID, "2",
                                                f"G1 {month}: target weight {targets.get(i, 0.0):.3f}",
                                                client_key=f"g1:{month}:{i}:{side}"), now)
        placed.append((i, side, str(abs(delta)), current_state(store, oid).value))
    return {"filled": filled, "decision": month, "targets": {k: round(v, 4) for k, v in targets.items()}, "orders": placed}


def shadow_ideas(store: Store, now: datetime, symbols: list[str], max_new: int = 3, fallback_marks: dict[str, Decimal] | None = None) -> dict:
    """Pre-register small hypothetical buys of top-ranked names the owner does not hold, in the SHADOW ledger only."""
    shadows = store.list_accounts(LedgerKind.SHADOW)
    if not shadows:
        return {"skipped": "no shadow account"}
    sh = shadows[-1].account_id
    state = state_from_entries(store, sh, now)
    hist = _hist(store, symbols, now)
    held = set(state.positions)
    out = []
    marks = {i: Decimal(str(bars_known_at(store, i, now)[-1].close)) for i in held if bars_known_at(store, i, now)}
    n = state.cash + sum((q * marks[i] for i, q in state.positions.items() if i in marks), ZERO)
    for idea in current_ideas(hist, held)[:max_new]:
        p = Decimal(str(hist[idea.instrument_id][-1].close))
        qty = _qty(Decimal(str(idea.suggested_weight)) * n, p)
        if qty < 1:
            continue
        oid = propose_order(store, OrderRequest(sh, idea.instrument_id, "BUY", str(qty), "G1_shadow_ideas", "2", idea.rationale,
                                                client_key=f"idea3:{now.date().isoformat()[:7]}:{idea.instrument_id}"), now, fallback_marks)
        out.append((idea.instrument_id, str(qty), current_state(store, oid).value))
    return {"orders": out}
