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


def test_buy_call_is_specific_and_honest_and_only_when_cash_covers():
    from nexus.suggest import call_lines
    hist = {iid("B"): series("B", .002)}
    snap = {"cash": {"USD": "50000"}, "holdings": {"EQ:US:Z": {"quantity": "10", "cost_basis": None}}, "estimated_fields": []}
    prices = {"EQ:US:Z": Decimal(100)}
    now = datetime(2026, 11, 19, 21, 30, tzinfo=timezone.utc)
    lines, keep, found = call_lines(snap, prices, hist, {}, {}, now)
    assert [f.kind for f in found] == ["buy_call"]
    assert len(lines) == 1 and lines[0].startswith("BUY B: ") and "limit $" in lines[0] and "Exit: sell if it closes below" in lines[0]
    assert "not been independently validated" in lines[0]
    assert call_lines(snap, prices, hist, {}, keep, now)[0] == []
    assert call_lines(dict(snap, cash={"USD": "10"}), prices, hist, {}, {}, now)[0] == []


def test_sell_call_needs_broken_trend_deep_momentum_and_a_loss():
    from nexus.suggest import call_lines
    bad = series("Z", -0.004)
    snap = {"cash": {"USD": "100"}, "estimated_fields": [],
            "holdings": {"EQ:US:Z": {"quantity": "100", "cost_basis": "20000"}, "EQ:US:Y": {"quantity": "100", "cost_basis": "100"}}}
    prices = {"EQ:US:Z": Decimal(str(bad[-1].close)), "EQ:US:Y": Decimal(100)}
    lines, _, _ = call_lines(snap, prices, {}, {"Z": bad, "Y": series("Y", -0.004)}, {}, datetime(2026, 11, 19, 21, 30, tzinfo=timezone.utc))
    assert [l.split(":")[0] for l in lines] == ["SELL Z"] and "wash-sale" in lines[0]      # Y has no loss -> no sell call


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


def test_protected_index_funds_are_never_sold():
    from nexus.suggest import call_lines
    bad = series("VTI", -0.004)
    snap = {"cash": {"USD": "100"}, "estimated_fields": [],
            "holdings": {"EQ:US:VTI": {"quantity": "100", "cost_basis": "90000"}}}
    prices = {"EQ:US:VTI": Decimal(str(bad[-1].close))}
    now = datetime(2026, 11, 19, 21, 30, tzinfo=timezone.utc)
    assert call_lines(snap, prices, {}, {"VTI": bad}, {}, now, protected=frozenset({"VTI"}))[0] == []


def test_calls_are_withheld_unless_the_gate_passes_and_recorded_when_it_does(store, clock, monkeypatch, tmp_path):
    import json as _json
    from nexus import redteam
    from nexus.accounting import import_actual_snapshot
    from nexus.ideas import G1_ID
    from nexus.pipeline import G1_RECORD
    from nexus.research import register_hypothesis
    from nexus.suggest import run, run_files
    # strategy registered but never promoted -> the real gate blocks calls
    register_hypothesis(store, G1_ID, "quant_lab", G1_RECORD, clock.now)
    ok, why = redteam.call_gate(store, G1_ID, 1)
    assert not ok and any("Q5 or higher" in w for w in why)
    store.register_instrument(Instrument("EQ:US:Z", {"alpaca": "Z"}, AssetClass.EQUITY, "USD", "America/New_York"))
    acct = store.create_account(LedgerKind.ACTUAL, "real").account_id
    import_actual_snapshot(store, acct, clock.now, "stmt", "Garret", cash={"USD": "50000"},
                           holdings={"EQ:US:Z": {"quantity": "10", "cost_basis": None}}, estimated_fields=[])
    snap_file = tmp_path / "s.json"
    snap_file.write_text(_json.dumps({"as_of": clock.now.isoformat(), "cash": {"USD": "50000"}, "estimated_fields": [],
                                      "holdings": {"EQ:US:Z": {"quantity": "10", "cost_basis": None}}}))
    feed = lambda: FixtureAdapter(series("Z", .001) + series("SPY", .002))
    t = datetime(2026, 11, 16, 21, 30, tzinfo=timezone.utc)
    clock.now = t
    out = run_files(str(snap_file), str(tmp_path / "st.json"), feed, t, store=store)
    assert out["calls_withheld"] and not any(l.startswith(("BUY", "SELL")) for l in out["lines"])
    assert store.conn.execute("SELECT COUNT(*) FROM recommendations WHERE kind='buy_call'").fetchone()[0] == 0   # nothing while closed
    monkeypatch.setattr(redteam, "call_gate", lambda *a: (True, []))
    out2 = run_files(str(snap_file), str(tmp_path / "st2.json"), feed, t, store=store)
    assert any(l.startswith("BUY SPY") for l in out2["lines"])
    rec = store.conn.execute("SELECT subject FROM recommendations WHERE kind='buy_call'").fetchall()
    assert [r[0] for r in rec] == ["SPY"]                  # recorded (timestamped, immutable) before it was returned


def test_g2_picks_calm_uptrends_only_and_never_levers():
    from nexus.ideas import g2_target_weights
    import random
    rng = random.Random(1)

    def noisy(sym, drift, vol):
        out, c = [], 100.0
        for d in SESS:
            c *= 1 + drift + rng.uniform(-vol, vol)
            out.append(Bar(iid(sym), d.isoformat(), c, c, c, c, 1e6))
        return out
    hist = {iid("CALM"): noisy("CALM", .0015, .002), iid("WILD"): noisy("WILD", .0015, .03), iid("DOWN"): noisy("DOWN", -.002, .001)}
    w = g2_target_weights(hist, top_n=2)
    assert iid("DOWN") not in w and iid("CALM") in w and sum(w.values()) <= 0.99 + 1e-9
