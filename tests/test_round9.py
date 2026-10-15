import importlib.util

import numpy as np
import pandas as pd

from core.config import ROOT
from core.market_calendar import trading_days

spec = importlib.util.spec_from_file_location("sh2", ROOT / "strategies" / "short_horizon_v2.py")
sh = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sh)


def panel(days=80, n=20, seed=3):
    index = pd.DatetimeIndex(trading_days("2020-02-03", "2020-12-31"))[:days]
    rng = np.random.default_rng(seed)
    close = pd.DataFrame(100 * np.cumprod(1 + rng.normal(0, 0.01, (days, n)), axis=0), index, [f"T{i:02d}" for i in range(n)])
    open_ = close.shift(1) * (1 + rng.normal(0, 0.003, (days, n)))
    snap = close * (1 + rng.normal(0, 0.002, (days, n)))
    return open_, close, snap


def test_rule_grid():
    ids = [r["id"] for r in sh.RULES]
    assert len(ids) == 9 and len(set(ids)) == 9
    assert {r["kind"] for r in sh.RULES} == {"plain", "band", "lv"} and {r["hold"] for r in sh.RULES} == {2, 5}


def test_snapshot_scores_use_snapshot_only_on_the_decision_day():
    open_, close, snap = panel()
    t = 30
    np.testing.assert_allclose(sh.score_matrix("rev1", open_, close, snap).iloc[t], -(snap.iloc[t] / close.iloc[t - 1] - 1))
    np.testing.assert_allclose(sh.score_matrix("rev5", open_, close, snap).iloc[t], -(snap.iloc[t] / close.iloc[t - 5] - 1))
    intraday = np.log(snap.iloc[t] / open_.iloc[t]) + sum(np.log(close.iloc[t - j] / open_.iloc[t - j]) for j in range(1, 5))
    np.testing.assert_allclose(sh.score_matrix("id5", open_, close, snap).iloc[t], -intraday)
    # with no snapshot the score is the round-8 close-timed one
    np.testing.assert_allclose(sh.score_matrix("rev1", open_, close, None).iloc[t], -(close.iloc[t] / close.iloc[t - 1] - 1))


def test_no_lookahead_in_snapshot_scores():
    open_, close, snap = panel()
    t = 30
    base = sh.score_matrix("rev5", open_, close, snap).iloc[t]
    later = close.copy()
    later.iloc[t + 1:] *= 3.0
    np.testing.assert_allclose(sh.score_matrix("rev5", open_, later, snap).iloc[t], base)


def test_missing_snapshot_means_not_ranked():
    open_, close, snap = panel()
    snap.iloc[30, 4] = np.nan
    assert np.isnan(sh.score_matrix("rev1", open_, close, snap).iloc[30, 4])


def test_volume_ratio():
    vol = pd.DataFrame({"A": np.r_[np.full(70, 100.0), np.full(5, 50.0)]})
    ratio = sh.volume_ratio(vol, 5)
    assert ratio.iloc[-1, 0] == 0.5


def run(rule, scores, ratio=None, n=20):
    open_, close, snap = panel(n=n)
    members = lambda dates: [frozenset(close.columns)] * len(dates)
    sh.FIRST_DECISION = str(close.index[10].date())
    decisions = sh.decision_dates(close.index, rule["hold"])
    return sh.generate_targets(rule, close, scores, ratio, decisions, members)


def test_plain_picks_top_decile_equal_weight():
    open_, close, snap = panel()
    rule = {"kind": "plain", "hold": 2, "signal": "rev1"}
    targets, detail = run(rule, sh.score_matrix("rev1", open_, close, snap))
    d = detail[3]
    assert len(d["picks"]) == 2
    weights = targets.loc[d["date"], d["picks"]]
    np.testing.assert_allclose(weights, 0.5)


def test_band_keeps_holdings_that_stay_in_top_30_percent():
    open_, close, snap = panel()
    scores = sh.score_matrix("rev1", open_, close, snap)
    plain, pd_ = run({"kind": "plain", "hold": 2, "signal": "rev1"}, scores)
    band, bd = run({"kind": "band", "hold": 2, "signal": "rev1"}, scores)
    held_prev = set(bd[0]["picks"])
    ranked = scores.loc[bd[1]["date"], bd[1]["ranked"]].sort_values(ascending=False)
    top30 = set(ranked.index[:6])
    assert set(bd[1]["picks"]) >= held_prev & top30
    assert all(len(d["picks"]) == 2 for d in bd)
    turnover = lambda t: t.dropna().diff().abs().sum().sum()
    assert turnover(band) <= turnover(plain)


def test_low_volume_filter_removes_high_volume_names():
    open_, close, snap = panel()
    scores = sh.score_matrix("rev1", open_, close, snap)
    ratio = pd.DataFrame(0.5, close.index, close.columns)
    ratio.iloc[:, :10] = 2.0
    _, detail = run({"kind": "lv", "hold": 2, "signal": "rev1"}, scores, ratio)
    assert all(not (set(d["ranked"]) & set(close.columns[:10])) for d in detail)


def test_snapshot_tracker_records_picks_and_nav(tmp_path):
    from core import snapshot_tracker as st
    open_, close, snap = panel(days=60, n=30)
    start = close.index[20]
    session = close.index[27]
    names = list(close.columns)
    membership = pd.Series([frozenset(names)], index=pd.DatetimeIndex(["2016-01-04"]))
    fake_close = lambda symbols, a, b: close.loc[:session]
    fake_snap = lambda symbols, day: snap.loc[day, [s for s in symbols]]
    cfg = {"rule": "stock_rev5_h2_band", "strategy_rule": "rev5_h2_band_s", "start": str(start.date()), "initial_cash": 1000}
    status = st.run_snapshot_rule(cfg, session, membership, tmp_path, fake_close, fake_snap)
    assert status["state"] == "running" and status["decisions"] == 4
    assert len(status["holdings"]) == 3 and status["decisions_changed_since_recorded"] == []
    assert (tmp_path / "decisions" / f"{start.date()}.json").exists() and (tmp_path / "nav.csv").exists()
    # a rerun reuses the stored snapshots even if the source now returns different prices
    again = st.run_snapshot_rule(cfg, session, membership, tmp_path, fake_close, lambda s, d: snap.loc[d, list(s)] * 2)
    assert again["holdings"] == status["holdings"] and again["decisions_changed_since_recorded"] == []


def test_v3_neighbour_grid():
    spec3 = importlib.util.spec_from_file_location("sh3", ROOT / "strategies" / "short_horizon_v3.py")
    sh3 = importlib.util.module_from_spec(spec3)
    spec3.loader.exec_module(sh3)
    ids = [r["id"] for r in sh3.RULES]
    assert len(ids) == 10 and ids[0] == "rev5_h2_band_s" and len(set(ids)) == 10
    open_, close, snap = panel(n=40)
    t = 30
    np.testing.assert_allclose(sh3.score_matrix("rev7", open_, close, snap).iloc[t], -(snap.iloc[t] / close.iloc[t - 7] - 1))
    row = pd.Series(np.arange(40.0), index=[f"T{i:02d}" for i in range(40)])
    wide = sh3.select({"kind": "band", "fraction": 0.15, "band": 0.3}, row, [])
    assert len(wide) == 6
    held = ["T25"]   # rank 15 of 40: outside the 20% band, inside the 40% band
    assert "T25" not in sh3.select({"kind": "band", "fraction": 0.1, "band": 0.2}, row, held)
    assert "T25" in sh3.select({"kind": "band", "fraction": 0.1, "band": 0.4}, row, held)


def test_snapshot_tracker_hold_three(tmp_path):
    from core import snapshot_tracker as st
    open_, close, snap = panel(days=60, n=30)
    start, session = close.index[20], close.index[29]
    names = list(close.columns)
    membership = pd.Series([frozenset(names)], index=pd.DatetimeIndex(["2016-01-04"]))
    cfg = {"rule": "stock_rev5_h3_band40", "strategy_rule": "rev5_h3_band40_s", "start": str(start.date()), "initial_cash": 1000}
    status = st.run_snapshot_rule(cfg, session, membership, tmp_path, lambda s, a, b: close.loc[:session],
                                  lambda symbols, day: snap.loc[day, list(symbols)])
    assert status["decisions"] == 4 and status["state"] == "running"   # sessions 20, 23, 26, 29
    assert st.decision_sessions(start, session, 3)[1] == close.index[23]


def test_snapshot_tracker_vixscale_weights(tmp_path):
    from core import snapshot_tracker as st
    open_, close, snap = panel(days=60, n=30)
    start, session = close.index[20], close.index[26]
    names = list(close.columns)
    membership = pd.Series([frozenset(names)], index=pd.DatetimeIndex(["2016-01-04"]))
    vix_index = pd.DatetimeIndex(trading_days("2019-01-02", "2020-12-31"))
    vix = pd.Series(20.0, vix_index)                      # share = clip(1 - 0.5) = 0.5 once 200 sessions exist
    vix = vix.reindex(vix.index.union(close.index)).ffill().dropna()
    cfg = {"rule": "stock_rev5_h3_band40_vixscale", "strategy_rule": "rev5_h3_band40_vixscale_s", "start": str(start.date()), "initial_cash": 1000}
    fake_vix = lambda: pd.Series(20.0, pd.bdate_range("2019-01-01", session))
    status = st.run_snapshot_rule(cfg, session, membership, tmp_path, lambda s, a, b: close.loc[:session],
                                  lambda symbols, day: snap.loc[day, list(symbols)], fake_vix)
    import json
    rec = json.loads((tmp_path / "decisions" / f"{start.date()}.json").read_text())
    assert abs(sum(rec["weights"].values()) - 1.0) < 1e-9
    assert abs(rec["active_share"] - 0.5) < 1e-9 and status["state"] == "running"
    # rerun reads the stored weights
    again = st.run_snapshot_rule(cfg, session, membership, tmp_path, lambda s, a, b: close.loc[:session],
                                 lambda s, d: snap.loc[d, list(s)] * 2, fake_vix)
    assert again["holdings"] == status["holdings"]
