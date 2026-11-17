import sqlite3
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from nexus.accounting import record_entry, state_from_entries
from nexus.adapters.fixture import FixtureAdapter
from nexus.calendars import NY, NyseCalendar
from nexus.domain import AssetClass, Bar, CapabilityTier, Instrument, LedgerKind, OrderState
from nexus.errors import LaunchBoundaryViolation, NexusError, StaleOrInvalidDataError, SystemHalted
from nexus.ingestion import ingest_daily_bars
from nexus.orders import OrderRequest, current_state, propose_order, transition
from nexus.simulator import try_fill

IID = "EQ:XNAS:AAPL"
cal = NyseCalendar()
SESS = cal.sessions_between(date(2026, 11, 2), date(2026, 11, 13))      # 10 sessions
UTC = timezone.utc


def bars(vol=1_000_000.0, upto=None):
    out = []
    for i, d in enumerate(SESS):
        c = 100 + i
        out.append(Bar(IID, d.isoformat(), c, c + 2, c - 2, c + 1, vol))
    return out[:upto] if upto else out


@pytest.fixture
def env(store, clock):
    store.register_instrument(Instrument(IID, {"alpaca": "AAPL"}, AssetClass.EQUITY, "USD", "America/New_York",
                                         capability_tier=CapabilityTier.R2))
    acct = store.create_account(LedgerKind.PAPER_SLEEVE, "momentum").account_id
    record_entry(store, acct, "DEPOSIT", clock.now, cash_delta="100000")
    return store, acct


def load(store, clock, upto):
    """Ingest the first `upto` sessions as of a fixed ingestion time."""
    ingest_daily_bars(store, FixtureAdapter(bars(upto=upto), clock=clock), IID, SESS[0], SESS[upto - 1])


def decide_at(d):          # decision at 18:00 NY on session d (after the close)
    return datetime.combine(d, datetime.min.time().replace(hour=18), tzinfo=NY).astimezone(UTC)


def req(acct, **kw):
    base = dict(account_id=acct, instrument_id=IID, side="BUY", quantity="10", strategy_id="s1", strategy_version="1",
                rationale="test")
    base.update(kw)
    return OrderRequest(**base)


def setup_decision(env, clock, n=5):
    store, acct = env
    load(store, clock, n)
    now = decide_at(SESS[n - 1])
    clock.now = now
    return store, acct, now


def test_decision_is_preregistered_before_fill(env, clock):
    store, acct, now = setup_decision(env, clock)
    oid = propose_order(store, req(acct), now)
    assert current_state(store, oid) is OrderState.ACCEPTED_BY_SIMULATOR
    row = store.conn.execute("SELECT * FROM orders WHERE order_id=?", (oid,)).fetchone()
    ev = [e for e in store.events.all() if e.event_id == row["decision_event_id"]][0]
    assert ev.event_type.value == "decision.recorded" and ev.occurred_at == now and ev.payload["risk_approved"]
    assert ev.payload["snapshots"] and row["data_snapshot_ids"] != "[]"


def test_no_lookahead_fill_waits_for_next_session_bar(env, clock):
    store, acct, now = setup_decision(env, clock, n=5)
    oid = propose_order(store, req(acct), now)
    assert try_fill(store, oid, now) is OrderState.ACCEPTED_BY_SIMULATOR          # no later bar exists yet
    assert state_from_entries(store, acct).positions == {}
    clock.advance(days=1)
    load(store, clock, 6)                                                           # session 6 bar ingested next day
    after_close = decide_at(SESS[5]) + timedelta(hours=1)
    clock.now = after_close
    assert try_fill(store, oid, after_close) is OrderState.FILLED
    assert try_fill(store, oid, after_close) is OrderState.FILLED                  # idempotent
    st = state_from_entries(store, acct)
    px = Decimal("105") * (1 + Decimal("7") / 10000)                                # session-6 open + 7 bps adverse
    assert st.positions[IID] == 10 and st.cash == 100000 - 10 * px.quantize(Decimal("0.0001"))


def test_fill_before_session_close_is_not_final(env, clock):
    store, acct, now = setup_decision(env, clock, n=5)
    oid = propose_order(store, req(acct), now)
    clock.advance(days=1)
    load(store, clock, 6)
    mid_session = datetime.combine(SESS[5], datetime.min.time().replace(hour=12), tzinfo=NY).astimezone(UTC)
    assert try_fill(store, oid, mid_session) is OrderState.ACCEPTED_BY_SIMULATOR


def test_sell_slippage_is_adverse_and_cash_reconciles(env, clock):
    store, acct = env
    record_entry(store, acct, "TRADE", clock.now, instrument_id=IID, qty_delta="20", price="100", cash_delta="-2000")
    store2, acct2, now = setup_decision(env, clock, 5)
    oid = propose_order(store, req(acct, side="SELL", quantity="10"), now)
    clock.advance(days=1); load(store, clock, 6)
    t = decide_at(SESS[5]) + timedelta(hours=1)
    clock.now = t
    try_fill(store, oid, t)
    px = (Decimal("105") * (1 - Decimal("7") / 10000)).quantize(Decimal("0.0001"))
    assert state_from_entries(store, acct).cash == 100000 - 2000 + 10 * px


def test_partial_fill_under_participation_cap_then_day_expiry(store, clock):
    store.register_instrument(Instrument(IID, {"v": "A"}, AssetClass.EQUITY, "USD", "America/New_York", capability_tier=CapabilityTier.R2))
    acct = store.create_account(LedgerKind.PAPER_SLEEVE, "m").account_id
    record_entry(store, acct, "DEPOSIT", clock.now, cash_delta="100000")
    ingest_daily_bars(store, FixtureAdapter(bars(vol=500.0, upto=5), clock=clock), IID, SESS[0], SESS[4])
    now = decide_at(SESS[4]); clock.now = now
    oid = propose_order(store, req(acct, quantity="20"), now)       # 1% of 500 = 5 shares/day
    clock.advance(days=1)
    ingest_daily_bars(store, FixtureAdapter(bars(vol=500.0, upto=6), clock=clock), IID, SESS[0], SESS[5])
    t = decide_at(SESS[5]) + timedelta(hours=1); clock.now = t
    assert try_fill(store, oid, t) is OrderState.EXPIRED
    states = [r["to_state"] for r in store.conn.execute("SELECT to_state FROM order_transitions WHERE order_id=? ORDER BY seq", (oid,))]
    assert "PARTIALLY_FILLED" in states and states[-1] == "EXPIRED"
    assert state_from_entries(store, acct).positions[IID] == 5


def test_limit_order_fills_only_if_reached_else_expires(env, clock):
    store, acct, now = setup_decision(env, clock, 5)
    far = propose_order(store, req(acct, order_type="LIMIT", limit_price="50"), now)
    near = propose_order(store, req(acct, order_type="LIMIT", limit_price="106"), now)
    clock.advance(days=1); load(store, clock, 6)
    t = decide_at(SESS[5]) + timedelta(hours=1); clock.now = t
    assert try_fill(store, far, t) is OrderState.EXPIRED
    assert try_fill(store, near, t) is OrderState.FILLED
    px = Decimal(next(__import__("json").loads(r["detail_json"])["fill_price"] for r in store.conn.execute(
        "SELECT detail_json FROM order_transitions WHERE order_id=? AND to_state='FILLED'", (near,))))
    assert px <= Decimal("106")


@pytest.mark.parametrize("kw,why", [
    (dict(quantity="100000"), "cash"),
    (dict(side="SELL", quantity="1"), "shorting"),
    (dict(quantity="300"), "max weight"),
])
def test_risk_gate_rejects_and_records(env, clock, kw, why):
    store, acct, now = setup_decision(env, clock, 5)
    oid = propose_order(store, req(acct, **kw), now)
    assert current_state(store, oid) is OrderState.REJECTED
    ev = [e for e in store.events.all() if e.event_type.value == "decision.recorded"][-1]
    assert ev.payload["risk_approved"] is False and ev.payload["risk_reasons"]


def test_low_tier_instrument_rejected(store, clock):
    store.register_instrument(Instrument(IID, {"v": "A"}, AssetClass.EQUITY, "USD", "America/New_York", capability_tier=CapabilityTier.R1))
    acct = store.create_account(LedgerKind.PAPER_SLEEVE, "m").account_id
    record_entry(store, acct, "DEPOSIT", clock.now, cash_delta="1000")
    load(store, clock, 5)
    now = decide_at(SESS[4]); clock.now = now
    assert current_state(store, propose_order(store, req(acct, quantity="1"), now)) is OrderState.REJECTED


def test_orders_cannot_target_actual_ledger(store, clock):
    actual = store.create_account(LedgerKind.ACTUAL, "real").account_id
    with pytest.raises(LaunchBoundaryViolation):
        propose_order(store, req(actual), clock.now)


def test_stale_data_halt_and_decision_timestamp_block(env, clock):
    store, acct, now = setup_decision(env, clock, 5)
    with pytest.raises(StaleOrInvalidDataError):                         # a week later with no new bars: stale
        late = now + timedelta(days=7); clock.now = late
        propose_order(store, req(acct), late)
    clock.now = now
    store.controls.halt("owner", "stop")
    with pytest.raises(SystemHalted):
        propose_order(store, req(acct), now)
    store.controls.resume("owner", "go")
    with pytest.raises(NexusError, match="backdating"):                  # decision timestamp must be contemporaneous
        propose_order(store, req(acct), now - timedelta(hours=3))


def test_state_machine_enforced_and_history_immutable(env, clock):
    store, acct, now = setup_decision(env, clock, 5)
    oid = propose_order(store, req(acct), now)
    with pytest.raises(NexusError, match="illegal"):
        transition(store, oid, OrderState.SETTLED, now)
    with pytest.raises(sqlite3.DatabaseError):
        store.conn.execute("UPDATE order_transitions SET to_state='FILLED'")
    with pytest.raises(sqlite3.DatabaseError):
        store.conn.execute("UPDATE orders SET quantity='1'")


def test_deterministic_replay(clock):
    from nexus.config import load_config
    from nexus.store import Store
    results = []
    for _ in range(2):
        s = Store(":memory:", load_config(), clock=clock)
        s.register_instrument(Instrument(IID, {"v": "A"}, AssetClass.EQUITY, "USD", "America/New_York", capability_tier=CapabilityTier.R2))
        a = s.create_account(LedgerKind.PAPER_SLEEVE, "m").account_id
        clock.now = datetime(2026, 11, 5, 12, tzinfo=UTC)
        record_entry(s, a, "DEPOSIT", clock.now, cash_delta="100000")
        load(s, clock, 5)
        now = decide_at(SESS[4]); clock.now = now
        oid = propose_order(s, req(a), now)
        clock.advance(days=1); load(s, clock, 6)
        t = decide_at(SESS[5]) + timedelta(hours=1); clock.now = t
        try_fill(s, oid, t)
        st = state_from_entries(s, a)
        results.append((st.cash, st.positions))
    assert results[0] == results[1]
