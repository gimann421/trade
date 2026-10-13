import importlib.util

import numpy as np
import pandas as pd
import pytest

from core.config import ROOT
from core.market_calendar import trading_days
from core.portfolio import month_ends

spec = importlib.util.spec_from_file_location("fs", ROOT / "strategies" / "factor_scan_v1.py")
fs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fs)


def panel(n=6, days=400, seed=3):
    index = pd.DatetimeIndex(trading_days("2019-01-01", "2020-09-30"))[:days]
    rng = np.random.default_rng(seed)
    r = rng.normal(0.0004, 0.01, (len(index), n)) * np.linspace(0.5, 2.0, n)  # rising volatility by column
    close = pd.DataFrame(100 * np.cumprod(1 + r, axis=0), index, [f"T{i}" for i in range(n)])
    market = pd.Series(100 * np.cumprod(1 + rng.normal(0.0004, 0.008, len(index))), index)
    return close, market


def test_rule_count_and_ids():
    ids = [r["id"] for r in fs.RULES]
    assert len(ids) == 37 and len(set(ids)) == 37
    assert sum(r["family"] == "etf" for r in fs.RULES) == 16
    assert sum(r["family"] == "stock" and not r["trend"] for r in fs.RULES) == 14
    assert sum(r.get("trend", False) for r in fs.RULES) == 7


def test_return_score_matches_direct_calculation_and_skip():
    close, _ = panel()
    t = 300
    got = fs.return_score(close, 252, 21).iloc[t]
    want = close.iloc[t - 21] / close.iloc[t - 253] - 1  # the 232 daily returns of days t-252..t-21
    pd.testing.assert_series_equal(got, want, check_names=False, rtol=1e-9)
    rev = fs.return_score(close, 20, 0, -1).iloc[t]
    pd.testing.assert_series_equal(rev, -(close.iloc[t] / close.iloc[t - 21] - 1), check_names=False, rtol=1e-9)


def test_return_score_ranks_only_names_with_enough_history():
    close, _ = panel()
    close.iloc[:150, 0] = np.nan  # T0 starts trading late
    close.iloc[200, 1] = np.nan   # T1 has one missing close: two missing returns in the window
    s = fs.return_score(close, 252, 21).iloc[300]
    assert np.isnan(s["T0"]) and np.isnan(s["T1"]) and s[["T2", "T3"]].notna().all()


def test_lowvol_beta_and_high52():
    close, market = panel()
    t = 330
    r = close.pct_change()
    assert fs.score_matrix("lowvol", close).iloc[t].idxmax() == "T0"
    for col in ("T2", "T4"):
        window = slice(t - 251, t)
        m = market.pct_change()
        slope = np.polyfit(m.iloc[window.start:t + 1], r[col].iloc[window.start:t + 1], 1)[0]
        assert -fs.score_matrix("lowbeta", close, market).loc[close.index[t], col] == pytest.approx(slope, rel=1e-9)
    ratio = fs.score_matrix("high52", close).iloc[t]
    assert ((ratio > 0) & (ratio <= 1 + 1e-12)).all()
    assert ratio.iloc[0] == pytest.approx(close.iloc[t, 0] / close.iloc[t - 251:t + 1, 0].max())


def test_trend_series_needs_a_full_window():
    market = pd.Series(np.linspace(100, 200, 260), pd.date_range("2020-01-01", periods=260, freq="B"))
    trend = fs.trend_series(market)
    assert not trend.iloc[:199].any() and trend.iloc[199:].all()
    assert not fs.trend_series(market[::-1].set_axis(market.index)).iloc[199:].any()


def test_pick_counts_and_ties():
    s = pd.Series({"B": 1.0, "A": 1.0, "C": 0.5, "D": np.nan})
    assert fs.pick(s, k=2) == ["A", "B"]
    assert fs.pick(s, fraction=0.5) == ["A", "B"]  # round(1.5) = 2 of 3 ranked
    assert fs.pick(pd.Series(dtype=float), k=2) == []


def test_targets_trend_off_goes_to_cash_and_benchmark_stays_invested(monkeypatch):
    monkeypatch.setattr(fs, "FIRST_DECISION", "2020-02-28")
    close, market = panel(days=380)
    close["BIL"] = 100.0
    scores = fs.score_matrix("mom12_1", close.drop(columns="BIL"))
    scores["BIL"] = np.nan
    decisions = close.index[month_ends(close.index)]
    first = pd.Timestamp(fs.FIRST_DECISION)
    rule = {"id": "x", "family": "etf", "tickers": ["T0", "T1", "T2", "T3"], "signal": "mom12_1", "k": 2, "trend": True}
    trend = pd.Series(True, close.index)
    off_day = [d for d in decisions if d >= first][1]
    trend.loc[off_day] = False
    strat, bench, detail = fs.generate_targets(rule, close, scores, decisions, trend=trend)
    on = [d for d in detail if not d["off"]][0]
    assert strat.loc[on["date"]].drop("BIL").gt(0).sum() == 2 and strat.loc[on["date"], "BIL"] == 0
    assert strat.loc[off_day, "BIL"] == 1.0 and strat.loc[off_day].drop("BIL").sum() == 0
    assert bench.loc[off_day, ["T0", "T1", "T2", "T3"]].eq(0.25).all() and bench.loc[off_day, "BIL"] == 0
    assert strat.loc[:first].iloc[:-1].isna().all().all()  # nothing before the common first decision


def test_stock_targets_follow_membership_and_no_lookahead(monkeypatch):
    monkeypatch.setattr(fs, "FIRST_DECISION", "2019-03-29")
    close, market = panel(n=10, days=420)
    close["BIL"] = 100.0
    names = [c for c in close.columns if c != "BIL"]
    membership = pd.Series([frozenset(names), frozenset(names) - {"T9"}],
                           index=pd.to_datetime(["2018-12-01", "2020-03-15"]))
    decisions = close.index[month_ends(close.index)]
    rule = {"id": "s", "family": "stock", "signal": "rev1", "fraction": 0.2, "trend": False}
    scores = fs.score_matrix("rev1", close.drop(columns="BIL"))
    scores["BIL"] = np.nan
    full, bench_full, detail = fs.generate_targets(rule, close, scores, decisions, membership)
    late = [d for d in detail if d["date"] > pd.Timestamp("2020-03-15")][0]
    assert "T9" not in late["priced"] and bench_full.loc[late["date"], "T9"] == 0
    assert len(late["picks"]) == 2 and full.loc[late["date"]].sum() == pytest.approx(1.0)
    cutoff = pd.Timestamp("2020-02-28")
    part_close = close.loc[:cutoff]
    part_scores = fs.score_matrix("rev1", part_close.drop(columns="BIL"))
    part_scores["BIL"] = np.nan
    part, part_bench, _ = fs.generate_targets(rule, part_close, part_scores,
                                              [d for d in decisions if d <= cutoff], membership)
    pd.testing.assert_frame_equal(part, full.loc[:cutoff])
    pd.testing.assert_frame_equal(part_bench, bench_full.loc[:cutoff])
