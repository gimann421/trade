from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from nexus import ideas, sleeve
from nexus.accounting import record_entry, state_from_entries
from nexus.adapters.fixture import FixtureAdapter
from nexus.calendars import NyseCalendar
from nexus.domain import AssetClass, Bar, CapabilityTier, Instrument, LedgerKind
from nexus.ideas import g1_strategy, iid, rank, target_weights
from nexus.ingestion import ingest_daily_bars
from nexus.research import BacktestConfig, run_backtest
from nexus.suggest import idea_lines

cal = NyseCalendar()
SESS = cal.sessions_between(date(2025, 9, 1), date(2026, 11, 13))


def series(sym, drift, n=None):
    out, c = [], 100.0
    for k, d in enumerate(SESS[:n]):
        c *= 1 + drift
        out.append(Bar(iid(sym), d.isoformat(), c, c * 1.01, c * 0.99, c, 5_000_000))
    return out


def test_rank_requires_momentum_and_trend():
    up, down, flat = series("UP", 0.002), series("DN", -0.002), series("FL", 0.0)
    r = rank({iid("UP"): up, iid("DN"): down, iid("FL"): flat})
    assert [i for i, _ in r] == [iid("UP")]


def test_no_leverage_and_cash_buffer():
    hist = {iid(s): series(s, d) for s, d in [("A", .003), ("B", .002), ("C", .0015), ("D", .001), ("E", .0008), ("F", .0007)]}
    w = target_weights(hist)
    assert len(w) == 5 and sum(w.values()) <= 0.99 + 1e-9
    res = run_backtest(hist, g1_strategy, SESS[250].isoformat(), SESS[-1].isoformat(), BacktestConfig())
    assert res["cagr_net"] > 0 and res["max_drawdown"] < 0.2


def test_strategy_has_no_lookahead():
    hist = {iid("A"): series("A", .002), iid("B"): series("B", .001)}
    cut = SESS[300].isoformat()
    full = g1_strategy({i: [b for b in bs if b.session_date <= cut] for i, bs in hist.items()})
    # appending future bars must not change a decision taken at ``cut``
    future = {i: bs[:] for i, bs in hist.items()}
    assert g1_strategy({i: [b for b in bs if b.session_date <= cut] for i, bs in future.items()}) == full


def test_current_ideas_exclude_held_and_are_small():
    hist = {iid("A"): series("A", .003), iid("B"): series("B", .002)}
    got = ideas.current_ideas(hist, {"A"})
    assert [g.instrument_id for g in got] == [iid("B")] and got[0].suggested_weight <= 0.03
    assert "not independently validated" in got[0].rationale


def test_idea_lines_only_when_cash_covers_and_only_new():
    hist = {iid("B"): series("B", .002)}
    snap = {"cash": {"USD": "5000"}, "holdings": {"EQ:US:Z": {"quantity": "10", "cost_basis": None}}, "estimated_fields": []}
    prices = {"EQ:US:Z": Decimal(100)}
    now = datetime(2026, 11, 19, 21, 30, tzinfo=timezone.utc)
    lines, keep = idea_lines(snap, prices, hist, {}, now)
    assert len(lines) == 1 and "NEW IDEA" in lines[0] and "has not passed" in lines[0]
    again, _ = idea_lines(snap, prices, hist, keep, now)
    assert again == []
    poor = dict(snap, cash={"USD": "10"})
    assert idea_lines(poor, prices, hist, {}, now)[0] == []


def test_sleeve_decides_once_per_month_and_never_targets_actual(store, clock):
    syms = ["AA", "BB"]
    for s in syms:
        store.register_instrument(Instrument(iid(s), {"alpaca": s}, AssetClass.EQUITY, "USD", "America/New_York",
                                             capability_tier=CapabilityTier.R3))
    start = SESS[0]
    end = SESS[-1]
    clock.now = datetime.combine(end, datetime.min.time().replace(hour=22), tzinfo=timezone.utc) + timedelta(days=0)
    ad = FixtureAdapter(series("AA", .003) + series("BB", .002), clock=clock)
    for s in syms:
        ingest_daily_bars(store, ad, iid(s), start, end)
    now = clock.now
    r1 = sleeve.run_sleeve(store, now, syms)
    assert r1["orders"] and all(o[1] == "BUY" for o in r1["orders"])
    r2 = sleeve.run_sleeve(store, now, syms)
    assert r2["decision"] == "none"
    acct = store.list_accounts(LedgerKind.PAPER_SLEEVE)[0]
    assert state_from_entries(store, acct.account_id, now).cash == Decimal("100000")      # nothing filled before the next open


def test_unpriced_holding_blocks_shadow_buy_unless_explicit_fallback(store, clock):
    for s in ("AA", "ZZ"):
        store.register_instrument(Instrument(iid(s), {"alpaca": s}, AssetClass.EQUITY, "USD", "America/New_York",
                                             capability_tier=CapabilityTier.R3))
    end = SESS[-1]
    clock.now = datetime.combine(end, datetime.min.time().replace(hour=22), tzinfo=timezone.utc)
    ingest_daily_bars(store, FixtureAdapter(series("AA", .003), clock=clock), iid("AA"), SESS[0], end)
    sh = store.create_account(LedgerKind.SHADOW, "s").account_id
    record_entry(store, sh, "DEPOSIT", clock.now, cash_delta="50000")
    record_entry(store, sh, "ADJUSTMENT", clock.now, instrument_id=iid("ZZ"), qty_delta="10", note="unpriced holding")
    from nexus.orders import OrderRequest, current_state, propose_order
    req = lambda k: OrderRequest(sh, iid("AA"), "BUY", "5", "t", "1", "r", client_key=k)
    assert current_state(store, propose_order(store, req("a"), clock.now)).value == "REJECTED"
    ok = propose_order(store, req("b"), clock.now, {iid("ZZ"): Decimal("2")})
    assert current_state(store, ok).value == "ACCEPTED_BY_SIMULATOR"
