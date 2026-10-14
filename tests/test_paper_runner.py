import json

import numpy as np
import pandas as pd
import pytest

from core import paper_runner as pr
from core.market_calendar import trading_days
from core.portfolio import simulate


def test_decision_dates_use_the_exchange_calendar():
    got = pr.decision_dates("2024-03-01", "2024-06-30")
    assert [str(d.date()) for d in got] == ["2024-03-28", "2024-04-30", "2024-05-31", "2024-06-28"]  # Good Friday, Fri Jun 28
    assert pr.decision_dates("2024-04-02", "2024-04-29") == []
    assert [str(d.date()) for d in pr.decision_dates("2024-04-30", "2024-04-30")] == ["2024-04-30"]


@pytest.mark.parametrize("now,expected", [
    ("2026-10-13 21:00", "2026-10-13"),   # 17:00 New York on a Tuesday
    ("2026-10-13 19:00", "2026-10-12"),   # 15:00 New York: today's session is not complete
    ("2026-10-17 15:00", "2026-10-16"),   # Saturday
    ("2026-10-12 12:00", "2026-10-09"),   # Monday morning
    ("2026-09-08 01:00", "2026-09-04"),   # Labor Day (Sep 7) weekend: Monday 9pm NY is Tue 01:00 UTC
])
def test_last_completed_session(now, expected):
    assert str(pr.last_completed_session(pd.Timestamp(now, tz="UTC")).date()) == expected


def test_plan_orders_whole_shares_sells_first_and_ignores_unmanaged():
    orders = pr.plan_orders(picks=["AAA", "BBB"], prices={"AAA": 30.0, "BBB": 400.0, "OLD": 10.0, "OTHER": 5.0},
                            positions={"AAA": 10, "OLD": 7, "OTHER": 99}, managed={"AAA", "OLD"}, budget=2000.0)
    assert orders == [
        {"symbol": "OLD", "side": "sell", "qty": 7, "price": 10.0},
        {"symbol": "AAA", "side": "buy", "qty": 23, "price": 30.0},   # floor(1000 / 30) = 33 minus 10 held
        {"symbol": "BBB", "side": "buy", "qty": 2, "price": 400.0},
    ]
    assert pr.plan_orders([], {"OLD": 10.0}, {"OLD": 7}, {"OLD"}, 1000.0) == [
        {"symbol": "OLD", "side": "sell", "qty": 7, "price": 10.0}]
    assert pr.plan_orders(["AAA"], {"AAA": 30.0}, {"AAA": 33}, set(), 1000.0) == []  # already at target


def panel(last="2020-09-30", n=30, seed=5):
    index = trading_days("2019-01-02", last)
    rng = np.random.default_rng(seed)
    tickers = [f"S{i:02d}" for i in range(n)]
    r = rng.normal(0.0004, 0.012, (len(index), n)) + np.linspace(-0.001, 0.001, n)
    data = pd.DataFrame(100 * np.cumprod(1 + r, axis=0), index, tickers)
    for etf in pr.FACTOR_ETFS:
        data[etf] = 100 * np.cumprod(1 + rng.normal(0.0003, 0.008, len(index)))
    data["BIL"] = 100 * np.cumprod(1 + np.full(len(index), 0.00005))
    return data


def membership_for(data):
    stocks = frozenset(c for c in data.columns if c.startswith("S"))
    return pd.Series([stocks], index=[pd.Timestamp("2018-12-01")])


def make_fetch(data):
    return lambda symbols, start, end: data.loc[pd.Timestamp(start):pd.Timestamp(end), [c for c in symbols if c in data.columns]]


CFG = {"rule": "stock_resmom6_1_decile", "start": "2020-06-30", "initial_cash": 100_000}


def test_waiting_before_the_first_decision(tmp_path):
    data = panel()
    status = pr.run_rule(CFG | {"start": "2020-09-30"}, pd.Timestamp("2020-09-29"), membership_for(data), make_fetch(data), tmp_path)
    assert status["state"] == "waiting" and status["first_decision"] == "2020-09-30"
    assert not (tmp_path / "nav.csv").exists()


def test_shadow_record_matches_the_backtest_engine_and_is_write_once(tmp_path):
    data = panel()
    membership, fetch = membership_for(data), make_fetch(data)
    session = pd.Timestamp("2020-08-31")
    status = pr.run_rule(CFG, session, membership, fetch, tmp_path)
    assert status["state"] == "running" and status["decisions"] == 3 and status["last_decision"] == "2020-08-31"
    assert len(status["holdings"]) == 3 and status["members_without_bars"] == []

    nav = pd.read_csv(tmp_path / "nav.csv", index_col="date", parse_dates=True)
    assert nav.index[0] == pd.Timestamp("2020-06-30") and nav.index[-1] == session
    # nothing is invested before the first decision closes, so the first day's return is only the buying cost
    assert nav["nav"].iloc[0] == pytest.approx(100_000 * (1 - 5e-4), rel=1e-9)
    # hold the recorded picks by hand: June 30 picks until July 31, July picks until Aug 31
    close = data.loc["2020-06-30":"2020-08-31"]
    targets = pd.DataFrame(np.nan, close.index, [c for c in data.columns if c.startswith("S")] + ["BIL"])
    for day in ("2020-06-30", "2020-07-31", "2020-08-31"):
        picks = json.loads((tmp_path / f"decisions/{day}.json").read_text())["picks"]
        targets.loc[day] = 0.0
        targets.loc[day, picks] = 1 / len(picks)
    by_hand = 100_000 * (1 + simulate(close[targets.columns], targets, 5.0)["returns"]).cumprod()
    pd.testing.assert_series_equal(nav["nav"], by_hand, check_names=False, rtol=1e-9)

    # a second run changes nothing; a tampered decision file is flagged and not overwritten
    before = (tmp_path / "decisions/2020-07-31.json").read_text()
    assert pr.run_rule(CFG, session, membership, fetch, tmp_path)["decisions_changed_since_recorded"] == []
    record = json.loads(before)
    record["picks"] = ["S00", "S01", "S02"]
    (tmp_path / "decisions/2020-07-31.json").write_text(json.dumps(record))
    flagged = pr.run_rule(CFG, session, membership, fetch, tmp_path)["decisions_changed_since_recorded"]
    assert [f["decision_date"] for f in flagged] == ["2020-07-31"]
    assert json.loads((tmp_path / "decisions/2020-07-31.json").read_text())["picks"] == ["S00", "S01", "S02"]


def test_earlier_session_is_unaffected_by_later_data(tmp_path):
    data = panel()
    membership = membership_for(data)
    a, b = tmp_path / "a", tmp_path / "b"
    pr.run_rule(CFG, pd.Timestamp("2020-07-31"), membership, make_fetch(data), a)
    pr.run_rule(CFG, pd.Timestamp("2020-07-31"), membership, make_fetch(data.loc[:"2020-07-31"]), b)
    assert (a / "decisions/2020-07-31.json").read_text() == (b / "decisions/2020-07-31.json").read_text()
    pd.testing.assert_frame_equal(pd.read_csv(a / "nav.csv"), pd.read_csv(b / "nav.csv"))


def test_stale_data_raises(tmp_path):
    data = panel(last="2020-08-28")
    with pytest.raises(pr.DataNotReady):
        pr.run_rule(CFG, pd.Timestamp("2020-08-31"), membership_for(data), make_fetch(data), tmp_path)


def test_preview_writes_nothing(tmp_path):
    data = panel()
    status = pr.run_rule(CFG | {"start": "2020-08-31"}, pd.Timestamp("2020-09-15"), membership_for(data), make_fetch(data), None)
    assert status["state"] == "running" and status["last_decision"] == "2020-08-31" and len(status["holdings"]) == 3
    assert list(tmp_path.iterdir()) == []


def test_check_plan_applies_the_risk_limits_in_sequence_and_sends_nothing():
    from core.risk import AccountState, RiskLimits

    picks = [f"S{i:02d}" for i in range(50)]
    prices = {p: 100.0 for p in picks}
    state = AccountState(equity=100_000.0, day_start_equity=100_000.0, positions={})
    orders = pr.plan_orders(picks, prices, {}, set(), budget=50_000.0)           # $1,000 a name = 10 shares
    assert len(orders) == 50 and all(o["qty"] == 10 for o in orders)
    old = RiskLimits(5.0, 50.0, 10, 5000.0, 2.0, False)
    new = RiskLimits(5.0, 60.0, 60, 5000.0, 2.0, False)
    blocked_old = [o for o in pr.check_plan(orders, state, old) if o["violations"]]
    assert len(blocked_old) == 40 and "max_open_positions" in blocked_old[0]["violations"][0]   # the 11th name onward
    assert not [o for o in pr.check_plan(orders, state, new) if o["violations"]]
    # a bad day blocks buys, and a full-size book against a 60% gross cap is blocked once the cap is reached
    down = AccountState(equity=97_000.0, day_start_equity=100_000.0, positions={})
    assert all(o["violations"] for o in pr.check_plan(orders, down, new))
    full = pr.plan_orders(picks, prices, {}, set(), budget=100_000.0)
    blocked_full = [o for o in pr.check_plan(full, state, new) if o["violations"]]
    assert 0 < len(blocked_full) < 50 and any("gross exposure" in v for o in blocked_full for v in o["violations"])
