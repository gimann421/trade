import sqlite3
from datetime import date, datetime, timedelta, timezone

import pytest

from nexus.adapters.fixture import FixtureAdapter
from nexus.calendars import NyseCalendar
from nexus.domain import AssetClass, Bar, CapabilityTier, Instrument
from nexus.errors import NexusError, StaleOrInvalidDataError
from nexus.ingestion import ingest_daily_bars
from nexus.promotion import COMMITTEE, QUANT, RED_TEAM, current_tier, decide, demote
from nexus.research import (BacktestConfig, evaluate_criteria, get_hypothesis, register_hypothesis, run_backtest,
                            run_experiment)

IID = "EQ:XNAS:AAPL"
cal = NyseCalendar()
SESS = cal.sessions_between(date(2025, 1, 2), date(2026, 10, 30))


def trending_bars(drift=0.0006):
    out, px = [], 100.0
    for i, d in enumerate(SESS):
        noise = 0.004 * ((i * 7919) % 11 - 5) / 5
        o = px
        c = px * (1 + drift + noise)
        out.append(Bar(IID, d.isoformat(), o, max(o, c) * 1.002, min(o, c) * 0.998, c, 1e6))
        px = c
    return out


def always_long(hist):
    return {i: 1.0 for i in hist}


def cash_only(hist):
    return {}


RECORD = dict(title="t", asset_universe=[IID], rationale="r", signal_definition="s", holding_period="d", entry_exit_sizing_risk="x",
              benchmark_and_alternatives="b", data_sources=["fixture"], train_period=["2025-01-01", "2025-07-01"],
              validation_period=["2025-07-01", "2026-01-01"], holdout_period=["2026-01-01", "2026-11-01"],
              known_biases="b", capacity_notes="c", cost_assumptions="7bps", failure_conditions="f",
              success_criteria=dict(min_cagr_net=0.05, max_drawdown=0.3, min_sharpe=0.5, min_trades=1),
              paper_plan=dict(min_days=30, min_fills=10))


@pytest.fixture
def env(store, clock):
    store.register_instrument(Instrument(IID, {"v": "A"}, AssetClass.EQUITY, "USD", "America/New_York", capability_tier=CapabilityTier.R2))
    snap, rep = ingest_daily_bars(store, FixtureAdapter(trending_bars(), clock=clock), IID, SESS[0], SESS[-1])
    assert rep.ok
    return store, snap.snapshot_id


def reg(store, clock, **over):
    rec = {**RECORD, **over}
    return register_hypothesis(store, "H1", "quant-agent", rec, clock.now)


def test_registration_requires_complete_falsifiable_record(store, clock):
    with pytest.raises(NexusError, match="missing"):
        register_hypothesis(store, "H", "a", {**RECORD, "failure_conditions": ""}, clock.now)
    with pytest.raises(NexusError, match="pre-register"):
        register_hypothesis(store, "H", "a", {**RECORD, "success_criteria": {"min_sharpe": 1}}, clock.now)
    with pytest.raises(NexusError, match="ordered"):
        register_hypothesis(store, "H", "a", {**RECORD, "holdout_period": ["2025-01-01", "2025-02-01"]}, clock.now)


def test_versions_immutable_and_hash_checked(store, clock):
    assert reg(store, clock) == 1 and reg(store, clock) == 2
    with pytest.raises(sqlite3.DatabaseError, match="immutable"):
        store.conn.execute("UPDATE hypotheses SET author='x'")
    store.conn.execute("DROP TRIGGER hypotheses_no_update")
    store.conn.execute("UPDATE hypotheses SET record_json='{}' WHERE version=1")
    with pytest.raises(StaleOrInvalidDataError):
        get_hypothesis(store, "H1", 1)


def test_no_experiment_before_registration(env, clock):
    store, sid = env
    with pytest.raises(NexusError, match="not registered"):
        run_experiment(store, "NOPE", 1, "train", always_long, [sid], BacktestConfig(), clock.now)


def test_backtest_is_deterministic_and_reproducible(env, clock):
    store, sid = env
    reg(store, clock)
    a = run_experiment(store, "H1", 1, "train", always_long, [sid], BacktestConfig(), clock.now)
    b = run_experiment(store, "H1", 1, "train", always_long, [sid], BacktestConfig(), clock.now)
    assert a["result_sha"] == b["result_sha"] and a["exp_id"] != b["exp_id"]
    assert a["cagr_net"] > 0 and a["trades"] >= 1


def test_costs_matter_and_cash_earns_nothing(env, clock):
    store, sid = env
    bars = {IID: trending_bars()}
    base = run_backtest(bars, always_long, "2025-01-01", "2025-07-01", BacktestConfig())
    pricey = run_backtest(bars, always_long, "2025-01-01", "2025-07-01", BacktestConfig(cost_multiplier=50))
    assert pricey["total_return"] < base["total_return"] and pricey["costs_paid"] > base["costs_paid"]
    flat = run_backtest(bars, cash_only, "2025-01-01", "2025-07-01", BacktestConfig())
    assert flat["total_return"] == 0 and flat["trades"] == 0


def test_no_lookahead_in_engine():
    bars = {IID: trending_bars()}
    seen = []
    def spy(hist):
        seen.append((max(b.session_date for b in hist[IID]), len(hist[IID])))
        return {IID: 1.0}
    run_backtest(bars, spy, "2025-03-01", "2025-04-01", BacktestConfig())
    # on each decision day the strategy sees history only up to that day
    assert all(last <= "2025-04-01" for last, _ in seen)
    assert [n for _, n in seen] == sorted(n for _, n in seen) and len(set(n for _, n in seen)) == len(seen)


def test_invalid_weights_and_leverage_rejected():
    bars = {IID: trending_bars()}
    for w in ({IID: 1.5}, {IID: -0.5}, {"EQ:X:Y": 0.1}):
        with pytest.raises(NexusError):
            run_backtest(bars, lambda h, w=w: w, "2025-03-01", "2025-04-01", BacktestConfig())


def test_holdout_single_use_and_universe_enforced(env, clock):
    store, sid = env
    reg(store, clock)
    run_experiment(store, "H1", 1, "holdout", always_long, [sid], BacktestConfig(), clock.now)
    with pytest.raises(NexusError, match="holdout has already been used"):
        run_experiment(store, "H1", 1, "holdout", always_long, [sid], BacktestConfig(), clock.now)
    with pytest.raises(sqlite3.DatabaseError):                     # database also enforces it
        store.conn.execute("INSERT INTO experiments VALUES ('x','H1',1,'holdout','t','c','c','[]','{}','s')")
    reg(store, clock)                                              # a new version gets its own holdout
    run_experiment(store, "H1", 2, "holdout", always_long, [sid], BacktestConfig(), clock.now)
    reg(store, clock, asset_universe=["EQ:OTHER:X"])
    with pytest.raises(NexusError, match="outside the registered universe"):
        run_experiment(store, "H1", 3, "train", always_long, [sid], BacktestConfig(), clock.now)


def test_evaluate_criteria():
    ok = dict(cagr_net=0.2, max_drawdown=0.1, sharpe=1.5, trades=10)
    c = RECORD["success_criteria"]
    assert evaluate_criteria(c, ok) == []
    assert len(evaluate_criteria(c, {**ok, "cagr_net": 0.0, "sharpe": 0.1})) == 2


# ---------------- promotion workflow ----------------
def full_run(env, clock):
    store, sid = env
    reg(store, clock)
    for seg in ("train", "validation", "holdout"):
        run_experiment(store, "H1", 1, seg, always_long, [sid], BacktestConfig(), clock.now)
    return store


def clean_commit(store, monkeypatch):
    monkeypatch.setattr("nexus.research.code_commit", lambda: "abc123")


def test_author_cannot_self_promote_and_tiers_cannot_be_skipped(env, clock, monkeypatch):
    clean_commit(env[0], monkeypatch)
    store = full_run(env, clock)
    assert current_tier(store, "H1", 1) == "Q0"
    with pytest.raises(NexusError, match="skipped"):
        decide(store, "H1", 1, "Q3", "pass", "red-agent", RED_TEAM, "x", clock.now)
    with pytest.raises(NexusError, match="author cannot"):          # not even the early tiers
        decide(store, "H1", 1, "Q1", "pass", "quant-agent", QUANT, "self", clock.now)
    assert decide(store, "H1", 1, "Q1", "pass", "quant-peer", QUANT, "rationale and data audit done", clock.now) == "Q1"
    assert decide(store, "H1", 1, "Q2", "pass", "quant-peer", QUANT, "train run", clock.now) == "Q2"
    with pytest.raises(NexusError, match="author cannot"):
        decide(store, "H1", 1, "Q3", "pass", "quant-agent", RED_TEAM, "self", clock.now, {"flaws_addressed_or_disclosed": ["x"]})
    with pytest.raises(NexusError, match="independent"):
        decide(store, "H1", 1, "Q3", "pass", "other-agent", QUANT, "wrong role", clock.now, {"flaws_addressed_or_disclosed": ["x"]})


def test_full_ladder_to_q7_grants_no_authority(env, clock, monkeypatch):
    clean_commit(env[0], monkeypatch)
    store = full_run(env, clock)
    decide(store, "H1", 1, "Q1", "pass", "quant-peer", QUANT, "ok", clock.now)
    decide(store, "H1", 1, "Q2", "pass", "quant-peer", QUANT, "ok", clock.now)
    with pytest.raises(NexusError, match="flaws"):
        decide(store, "H1", 1, "Q3", "pass", "red", RED_TEAM, "ok", clock.now)
    decide(store, "H1", 1, "Q3", "pass", "red", RED_TEAM, "challenged", clock.now, {"flaws_addressed_or_disclosed": ["in-sample trend"]})
    decide(store, "H1", 1, "Q4", "pass", "committee", COMMITTEE, "criteria met", clock.now)
    with pytest.raises(NexusError, match="execution model"):
        decide(store, "H1", 1, "Q5", "pass", "committee", COMMITTEE, "ok", clock.now)
    decide(store, "H1", 1, "Q5", "pass", "committee", COMMITTEE, "ok", clock.now, {"execution_model_reviewed": True, "monitoring_ready": True})
    with pytest.raises(NexusError, match="minimums"):
        decide(store, "H1", 1, "Q6", "pass", "committee", COMMITTEE, "ok", clock.now, {"paper_days": 5, "paper_fills": 1})
    decide(store, "H1", 1, "Q6", "pass", "committee", COMMITTEE, "ok", clock.now, {"paper_days": 45, "paper_fills": 12})
    assert decide(store, "H1", 1, "Q7", "pass", "committee", COMMITTEE, "eligible for human review", clock.now) == "Q7"
    from nexus import permissions
    assert permissions.Capability.SUBMIT_REAL_ORDER in permissions.LAUNCH_FORBIDDEN       # unchanged by Q7
    with pytest.raises(NexusError):
        decide(store, "H1", 1, "Q7", "pass", "committee", COMMITTEE, "again", clock.now)   # no tier above Q7


def test_q4_blocked_when_criteria_fail_or_commit_unknown(env, clock, monkeypatch):
    store, sid = env
    monkeypatch.setattr("nexus.research.code_commit", lambda: "unknown")
    reg(store, clock)
    for seg in ("train", "validation", "holdout"):
        run_experiment(store, "H1", 1, seg, always_long, [sid], BacktestConfig(), clock.now)
    decide(store, "H1", 1, "Q1", "pass", "quant-peer", QUANT, "ok", clock.now)
    decide(store, "H1", 1, "Q2", "pass", "quant-peer", QUANT, "ok", clock.now)
    decide(store, "H1", 1, "Q3", "pass", "red", RED_TEAM, "ok", clock.now, {"flaws_addressed_or_disclosed": ["x"]})
    with pytest.raises(NexusError, match="reproducible"):
        decide(store, "H1", 1, "Q4", "pass", "committee", COMMITTEE, "ok", clock.now)
    # a hypothesis whose pre-registered bar is not met cannot be waved through
    monkeypatch.setattr("nexus.research.code_commit", lambda: "abc")
    register_hypothesis(store, "H2", "quant-agent", {**RECORD, "success_criteria": {**RECORD["success_criteria"], "min_sharpe": 99}}, clock.now)
    for seg in ("train", "validation", "holdout"):
        run_experiment(store, "H2", 1, seg, always_long, [sid], BacktestConfig(), clock.now)
    for t, who, role, ev in [("Q1", "quant-peer", QUANT, {}), ("Q2", "quant-peer", QUANT, {}), ("Q3", "red", RED_TEAM, {"flaws_addressed_or_disclosed": ["x"]})]:
        decide(store, "H2", 1, t, "pass", who, role, "ok", clock.now, ev)
    with pytest.raises(NexusError, match="criteria failed"):
        decide(store, "H2", 1, "Q4", "pass", "committee", COMMITTEE, "trust me", clock.now)


def test_fail_defer_demote_and_append_only(env, clock, monkeypatch):
    clean_commit(env[0], monkeypatch)
    store = full_run(env, clock)
    decide(store, "H1", 1, "Q1", "pass", "quant-peer", QUANT, "ok", clock.now)
    assert decide(store, "H1", 1, "Q2", "defer", "quant-peer", QUANT, "need more data", clock.now) == "Q1"
    assert decide(store, "H1", 1, "Q2", "fail", "quant-peer", QUANT, "no", clock.now) == "Q1"
    decide(store, "H1", 1, "Q2", "pass", "quant-peer", QUANT, "ok", clock.now)
    assert demote(store, "H1", 1, "Q0", "anyone", "owner", "regime change", clock.now) == "Q0"
    assert current_tier(store, "H1", 1) == "Q0"
    with pytest.raises(NexusError):
        demote(store, "H1", 1, "Q2", "anyone", "owner", "up is not a demotion", clock.now)
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        store.conn.execute("DELETE FROM promotion_decisions")
