import importlib.util

import numpy as np
import pandas as pd

from core.config import ROOT
from core.market_calendar import trading_days

spec = importlib.util.spec_from_file_location("sh4", ROOT / "strategies" / "short_horizon_v4.py")
sh4 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sh4)
spec3 = importlib.util.spec_from_file_location("sh3", ROOT / "strategies" / "short_horizon_v3.py")
sh3 = importlib.util.module_from_spec(spec3)
spec3.loader.exec_module(sh3)


def panel(days=60, n=40, seed=4):
    index = pd.DatetimeIndex(trading_days("2020-02-03", "2020-12-31"))[:days]
    rng = np.random.default_rng(seed)
    cols = [f"T{i:02d}" for i in range(n)]
    close = pd.DataFrame(100 * np.cumprod(1 + rng.normal(0, 0.01, (days, n)), axis=0), index, cols)
    open_ = close.shift(1) * (1 + rng.normal(0, 0.003, (days, n)))
    s45 = close * (1 + rng.normal(0, 0.002, (days, n)))
    s30 = s45 * (1 + rng.normal(0, 0.002, (days, n)))
    return open_, close, s45, s30


def test_grid():
    ids = [r["id"] for r in sh4.RULES]
    assert len(ids) == 9 and len(set(ids)) == 9
    assert {r["parent"] for r in sh4.RULES} >= {"rev5_h3_band40_s", "rev5_h2_band_s"}


def test_select_matches_v3():
    row = pd.Series(np.random.default_rng(1).normal(size=50), index=[f"T{i:02d}" for i in range(50)])
    held = list(row.index[:4])
    rule = {"kind": "band", "fraction": 0.1, "band": 0.4}
    assert sh4.select(rule, row, held) == sh3.select(rule, row, held)


def test_l15_scores_and_blend_inputs():
    open_, close, s45, s30 = panel()
    t = 30
    np.testing.assert_allclose(sh4.score_matrix("l15rev", open_, close, s45, s30).iloc[t], -(s45.iloc[t] / s30.iloc[t] - 1))
    np.testing.assert_allclose(sh4.score_matrix("l15mom", open_, close, s45, s30).iloc[t], s45.iloc[t] / s30.iloc[t] - 1)
    np.testing.assert_allclose(sh4.score_matrix("rev5", open_, close, s45, s30).iloc[t], -(s45.iloc[t] / close.iloc[t - 5] - 1))


def test_neutralize_groups():
    row = pd.Series([1, 2, 3, 4, 5, 6, 10.0, 20.0], index=list("abcdefgh"))
    groups = pd.Series({"a": "10", "b": "10", "c": "10", "d": "10", "e": "10", "f": "20", "g": "20"})   # h has no code
    out = sh4.neutralize(row, groups)
    assert np.isclose(out["a"], 1 - 3.0) and np.isclose(out["e"], 5 - 3.0)
    assert np.isclose(out["f"], 6 - row.mean())      # group of 2 -> market mean
    assert np.isclose(out["h"], 20 - row.mean())     # no code -> market mean


def test_exclusion_mask_window():
    index = pd.DatetimeIndex(trading_days("2020-02-03", "2020-03-31"))
    events = pd.DataFrame({"symbol": ["A"], "reaction": [index[10]]})
    mask = sh4.exclusion_mask(events, index, ["A", "B"])
    assert list(mask["A"].to_numpy().nonzero()[0]) == [10, 11, 12, 13, 14]
    assert not mask["B"].any()


def test_top_up_weights():
    held_w = pd.Series({"a": 0.5, "b": 0.5})
    growth = pd.Series({"a": 1.2, "b": 0.8})            # drifted: a 0.6, b 0.4
    w = sh4.top_up_weights(["a", "c"], held_w, growth)
    assert np.isclose(w["a"], 0.6) and np.isclose(w["c"], 0.4) and np.isclose(w.sum(), 1)
    only_kept = sh4.top_up_weights(["a"], held_w, growth)
    assert np.isclose(only_kept["a"], 1.0)


def test_no_top_up_targets_sum_to_one_and_keep_drift():
    open_, close, s45, s30 = panel()
    rule = next(r for r in sh4.RULES if r["id"] == "rev5_h2_band_nt_s")
    scores = sh4.score_matrix("rev5", open_, close, s45, s30)
    decisions = list(close.index[10::2])
    members = lambda ds: [list(close.columns)] * len(ds)
    sh4.FIRST_DECISION = str(close.index[10].date())
    strat, detail = sh4.generate_targets(rule, close, scores, decisions, members)
    rows = strat.dropna(how="all")
    assert np.allclose(rows.sum(axis=1), 1.0)
    # a name kept across two decisions has its drifted weight, not 1/n
    a, b = detail[3]["picks"], detail[4]["picks"]
    kept = [t for t in b if t in a]
    d3, d4 = rows.index[3], rows.index[4]
    assert kept
    prior = rows.loc[d3, a]
    drift = prior * close.loc[d4, a] / close.loc[d3, a]
    drift = drift / drift.sum()
    np.testing.assert_allclose(rows.loc[d4, kept], drift[kept])
    assert all(len(d["picks"]) == 4 for d in detail)


def _v5():
    spec5 = importlib.util.spec_from_file_location("sh5", ROOT / "strategies" / "short_horizon_v5.py")
    m = importlib.util.module_from_spec(spec5)
    spec5.loader.exec_module(m)
    return m


def test_v5_vix_share():
    sh5 = _v5()
    index = pd.DatetimeIndex(trading_days("2019-01-02", "2020-12-31"))
    vix = pd.Series(20.0, index)
    vix.iloc[400] = 40.0
    gate = sh5.vix_share(vix, index, "gate")
    scale = sh5.vix_share(vix, index, "scale")
    assert gate.iloc[300] == 0.0 and gate.iloc[401] == 1.0 and np.isnan(gate.iloc[10])   # decided on the previous close
    assert gate.iloc[400] == 0.0                                                          # the spike is not yet known
    assert np.isclose(scale.iloc[300], 0.5) and np.isclose(scale.iloc[401], 1.0)


def test_v5_residual_removes_beta():
    sh5 = _v5()
    open_, close, s45, s30 = panel(days=120, n=30, seed=9)
    market = close.pct_change().mean(axis=1)
    # a name that is exactly 2x the market has a residual of zero when snapshots equal closes
    close["T00"] = 100 * (1 + 2 * market.fillna(0)).cumprod()
    snap = close.copy()
    res = sh5.residual_matrix(close, snap)
    assert abs(res["T00"].iloc[-1]) < abs(res.drop(columns="T00").iloc[-1]).median()


def test_v5_targets_mix_equal_weight():
    sh5 = _v5()
    open_, close, s45, s30 = panel()
    rule = next(r for r in sh5.RULES if r["id"] == "rev5_h3_band40_vixscale_s")
    sh5.FIRST_DECISION = str(close.index[10].date())
    scores = sh5.rev5_matrix(close, s45)
    share = pd.Series(0.5, close.index)
    strat, detail = sh5.generate_targets(rule, close, scores, list(close.index[10::3]), lambda ds: [list(close.columns)] * len(ds), share=share)
    row = strat.dropna(how="all").iloc[0]
    assert np.isclose(row.sum(), 1.0)
    picks = detail[0]["picks"]
    assert np.isclose(row[picks[0]], 0.5 / len(picks) + 0.5 / 40)


def test_v5_volume_filter_drops_high_volume():
    sh5 = _v5()
    vol = pd.DataFrame(100.0, pd.date_range("2020-01-01", periods=80), ["A", "B"])
    vol.loc[vol.index[-5:], "A"] = 400.0
    ratio = sh5.volume_ratio(vol, 5)
    assert ratio["A"].iloc[-1] > sh5.VOLUME_LIMIT >= ratio["B"].iloc[-1]
