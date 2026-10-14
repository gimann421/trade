import importlib.util

import numpy as np
import pandas as pd
import pytest

from core.config import ROOT
from core.market_calendar import trading_days
from research import round8_short_horizon as r8

spec = importlib.util.spec_from_file_location("sh", ROOT / "strategies" / "short_horizon_v1.py")
sh = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sh)


def panel(days=40, n=5, seed=2):
    index = pd.DatetimeIndex(trading_days("2020-02-03", "2020-12-31"))[:days]
    rng = np.random.default_rng(seed)
    close = pd.DataFrame(100 * np.cumprod(1 + rng.normal(0, 0.01, (days, n)), axis=0), index, [f"T{i}" for i in range(n)])
    open_ = close.shift(1) * (1 + rng.normal(0, 0.003, (days, n)))
    return open_, close


def test_rule_grid():
    ids = [r["id"] for r in sh.RULES]
    assert len(ids) == 19 and len(set(ids)) == 19
    assert sum(r["fraction"] == 0.2 for r in sh.RULES) == 5 and {r["hold"] for r in sh.RULES} == {1, 2, 5, 10}
    assert "rev1_h5_q" in ids and "id5_h10" in ids


def test_scores_match_direct_calculation():
    open_, close = panel()
    t = 20
    np.testing.assert_allclose(sh.score_matrix("rev1", open_, close).iloc[t], -(close.iloc[t] / close.iloc[t - 1] - 1))
    np.testing.assert_allclose(sh.score_matrix("rev5", open_, close).iloc[t], -(close.iloc[t] / close.iloc[t - 5] - 1))
    np.testing.assert_allclose(sh.score_matrix("rev10", open_, close).iloc[t], -(close.iloc[t] / close.iloc[t - 10] - 1))
    overnight = sum(np.log(open_.iloc[t - j] / close.iloc[t - j - 1]) for j in range(5))
    np.testing.assert_allclose(sh.score_matrix("on5", open_, close).iloc[t], overnight)
    intraday = sum(np.log(close.iloc[t - j] / open_.iloc[t - j]) for j in range(5))
    np.testing.assert_allclose(sh.score_matrix("id5", open_, close).iloc[t], -intraday)
    # a missing price inside the window removes the name for that day
    open_.iloc[t - 2, 0] = np.nan
    assert np.isnan(sh.score_matrix("on5", open_, close).iloc[t, 0]) and np.isfinite(sh.score_matrix("on5", open_, close).iloc[t, 1])


def test_decision_dates_start_at_the_first_decision_and_step_by_the_hold():
    index = pd.DatetimeIndex(trading_days("2016-12-01", "2017-03-31"))
    assert str(sh.decision_dates(index, 5)[0].date()) == "2016-12-30"
    d1, d5 = sh.decision_dates(index, 1), sh.decision_dates(index, 5)
    assert d1[0] == d5[0] and index.get_loc(d5[1]) - index.get_loc(d5[0]) == 5 and len(d1) == len(index) - index.get_loc(d1[0])


def test_dirty_sessions_are_the_ten_march_2020_sessions():
    index = pd.DatetimeIndex(trading_days("2020-02-03", "2020-04-30"))
    dirty = r8.dirty_index(index)
    assert str(dirty[0].date()) == "2020-03-09" and str(dirty[-1].date()) == "2020-03-20" and len(dirty) == 10
    run = {"returns": pd.Series(0.01, index), "traded": pd.Series(0.1, index)}
    assert len(r8.cleaned(run, dirty)["returns"]) == len(index) - 10


def test_placebo_skips_holding_periods_that_touch_excluded_sessions():
    index = pd.DatetimeIndex(trading_days("2020-02-03", "2020-04-30"))
    rng = np.random.default_rng(0)
    close = pd.DataFrame(100 * np.cumprod(1 + rng.normal(0, 0.01, (len(index), 6)), axis=0), index, list("ABCDEF"))
    dates = list(index[::5])
    detail = [{"date": d, "priced": list(close.columns), "ranked": list(close.columns), "picks": ["A", "B"]} for d in dates]
    dirty = r8.dirty_index(index)
    _, pct_all = r8.placebo(detail, close, index, "2020-01-01", None, [])
    mean_skip, pct_skip = r8.placebo(detail, close, index, "2020-01-01", None, dirty)
    assert 0 <= pct_skip <= 1 and 0 <= pct_all <= 1
    kept = [w for w in __import__("research.round5_verdicts", fromlist=["x"]).holding_windows(detail, index)
            if not any(day in set(dirty) for day in index[(index >= w[1]) & (index <= w[2])])]
    assert 0 < len(kept) < len(dates) - 1


def test_weeks_to_confidence_and_break_even():
    assert r8.weeks_to_confidence(1.0) == pytest.approx(52 * 4)
    assert r8.weeks_to_confidence(0.5) == pytest.approx(52 * 16)
    assert r8.weeks_to_confidence(0.0) is None and r8.weeks_to_confidence(-0.3) is None
    assert r8.break_even_bps(0.05, 10.0) == pytest.approx(50.0)  # 5% gross on 10 units of turnover breaks even at 50 bps per unit
    assert r8.break_even_bps(0.05, 0.0) is None


GOOD = {"net_active": 0.05, "information_ratio": 0.6}


def test_judge_applies_the_bar_then_the_execution_checks():
    assert r8.judge("IS", 100, GOOD, 0.99, 0.01, 0.01) == ("supports", ["passes the bar and both execution checks"], False)
    verdict, why, sensitive = r8.judge("IS", 100, GOOD, 0.99, -0.01, 0.01)
    assert verdict == "contradicts" and sensitive and "delayed-fill" in why[0]
    verdict, why, sensitive = r8.judge("OOS", 100, GOOD, 0.99, 0.01, 0.0)
    assert verdict == "contradicts" and sensitive and "10 bps" in why[0]
    verdict, why, sensitive = r8.judge("IS", 100, {"net_active": 0.01, "information_ratio": 0.6}, 0.99, 0.01, 0.01)
    assert verdict == "contradicts" and not sensitive and "net active" in why[0]
    assert r8.judge("IS", 100, GOOD, 0.9, 0.01, 0.01)[0] == "contradicts"
    assert r8.judge("IS", 10, GOOD, 0.99, 0.01, 0.01)[0] == "inconclusive"
