import importlib.util

import numpy as np
import pandas as pd
import pytest

from core.config import ROOT
from core.market_calendar import trading_days
from core.portfolio import month_ends

spec = importlib.util.spec_from_file_location("rm", ROOT / "strategies" / "residual_momentum_v1.py")
rm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rm)

SMALL = {"start_lag": 40, "end_lag": 5, "min_valid": 35, "decile": 0.2}


def synthetic(n_stocks=10, seed=1):
    index = pd.DatetimeIndex(trading_days("2020-01-01", "2020-12-31"))
    rng = np.random.default_rng(seed)
    factors = pd.DataFrame(rng.normal(0, 0.01, (len(index), 3)), index, ["MKT", "SMB", "HML"])
    factors.iloc[0] = np.nan
    tickers = [f"S{i:02d}" for i in range(n_stocks)]
    alpha = np.linspace(-0.002, 0.002, n_stocks)  # S09 has the most stock-specific return
    beta = rng.uniform(0.5, 1.5, (3, n_stocks))
    ret = alpha + factors.fillna(0).to_numpy() @ beta + rng.normal(0, 0.01, (len(index), n_stocks))
    close = pd.DataFrame(100 * np.cumprod(1 + ret, axis=0), index, tickers)
    membership = pd.Series([frozenset(tickers)], index=[pd.Timestamp("2019-12-01")])
    return close, factors, membership


def test_residual_score_ranks_alpha_not_factor_exposure():
    index = pd.DatetimeIndex(trading_days("2020-01-01", "2020-06-30"))
    rng = np.random.default_rng(0)
    mkt = np.full(len(index), 0.01)  # a factor that rallies every day
    factors = pd.DataFrame({"MKT": mkt + rng.normal(0, 0.005, len(index)),
                            "SMB": rng.normal(0, 0.005, len(index)), "HML": rng.normal(0, 0.005, len(index))}, index)
    noise = rng.normal(0, 0.01, (len(index), 2))
    returns = pd.DataFrame({"BETA": 2.0 * factors["MKT"] + noise[:, 0],      # big raw return, no alpha
                            "ALPHA": 0.002 + 0.5 * factors["MKT"] + noise[:, 1]}, index)
    t_pos = len(index) - 1
    res = rm.residual_scores(returns, factors, t_pos, ["BETA", "ALPHA"], 100, 5, 90)
    raw = rm.total_return_scores(returns, factors, t_pos, ["BETA", "ALPHA"], 100, 5, 90)
    assert raw["BETA"] > raw["ALPHA"]
    assert res["ALPHA"] > res["BETA"]


def test_residual_score_matches_direct_regression_with_gaps():
    close, factors, _ = synthetic()
    returns = close.pct_change(fill_method=None)
    returns.iloc[100, 3] = np.nan  # S03 misses one day in the window (35 of 36 valid)
    t_pos = 120
    got = rm.residual_scores(returns, factors, t_pos, list(close.columns), 40, 5, 35)
    for ticker in ("S03", "S07"):
        y = returns[ticker].iloc[t_pos - 40:t_pos - 5 + 1]
        f = factors.iloc[t_pos - 40:t_pos - 5 + 1]
        ok = y.notna() & f.notna().all(axis=1)
        x = np.column_stack([np.ones(ok.sum()), f[ok].to_numpy()])
        b = np.linalg.lstsq(x, y[ok].to_numpy(), rcond=None)[0]
        resid = y[ok].to_numpy() - x[:, 1:] @ b[1:]
        assert got[ticker] == pytest.approx(resid.mean() / resid.std(ddof=1))
    # too few valid returns -> not ranked
    returns.iloc[90:92, 5] = np.nan
    assert "S05" not in rm.residual_scores(returns, factors, t_pos, list(close.columns), 40, 5, 35)


def test_top_decile_rounding_and_ties():
    scores = pd.Series({"B": 1.0, "A": 1.0, "C": 0.5, "D": 0.1, "E": -1, "F": 0, "G": 0, "H": 0, "I": 0, "J": 0,
                        "K": 0, "L": 0, "M": 0, "N": 0, "O": 0})
    assert rm.top_decile(scores, 0.1) == ["A", "B"]  # round(1.5) = 2, tie broken by name
    assert rm.top_decile(pd.Series(dtype=float), 0.1) == []


def test_weights_follow_membership_and_prices():
    close, factors, _ = synthetic()
    dates = close.index[month_ends(close.index)]
    # S09 (highest alpha) leaves the index in June; S00 has no close on the June month-end
    membership = pd.Series([frozenset(close.columns), frozenset(close.columns) - {"S09"}],
                           index=pd.to_datetime(["2019-12-01", "2020-06-15"]))
    close.loc["2020-06-30", "S00"] = np.nan
    strat, bench, detail = rm.generate_weights(close, factors, membership, dates, **SMALL)
    first = detail[0]["date"]
    assert first == pd.Timestamp("2020-03-31")  # Feb end has < 35 valid returns in its window
    assert strat.loc[:first].iloc[:-1].isna().all().all()
    assert np.allclose(strat.dropna().sum(axis=1), 1) and np.allclose(bench.dropna().sum(axis=1), 1)
    june = pd.Timestamp("2020-06-30")
    assert strat.loc[june, "S09"] == 0 and bench.loc[june, "S09"] == 0
    assert bench.loc[june, "S00"] == 0 and bench.loc[june].gt(0).sum() == 8
    assert (strat.loc[june] > 0).sum() == 2  # round(0.2 x 8 ranked)
    picks = [d["picks"] for d in detail if d["date"] < june]
    assert sum("S09" in p for p in picks) >= 2  # it ranks well while a member


def test_no_lookahead():
    close, factors, membership = synthetic()
    dates = close.index[month_ends(close.index)]
    full, full_b, _ = rm.generate_weights(close, factors, membership, dates, **SMALL)
    for cutoff in ("2020-07-31", "2020-09-15", "2020-11-30"):
        part, part_b, _ = rm.generate_weights(close.loc[:cutoff], factors.loc[:cutoff], membership,
                                              [d for d in dates if d <= pd.Timestamp(cutoff)], **SMALL)
        pd.testing.assert_frame_equal(part, full.loc[:cutoff])
        pd.testing.assert_frame_equal(part_b, full_b.loc[:cutoff])
