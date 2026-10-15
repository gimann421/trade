import importlib.util
import sys

import numpy as np
import pandas as pd

from core.config import ROOT


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "strategies" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sh = load("short_horizon_v6")
sys.path.insert(0, str(ROOT))
from research import round13_events as ev  # noqa: E402
from research import round13_weekday as wd  # noqa: E402


def sessions(n=40):
    return pd.bdate_range("2020-01-02", periods=n)


def test_sv_uses_only_previous_five_sessions():
    idx = sessions(12)
    short = pd.DataFrame({"A": np.arange(1.0, 13.0)}, index=idx)
    total = pd.DataFrame({"A": np.full(12, 10.0)}, index=idx)
    out = sh.sv_matrix(short, total, idx)
    assert out["A"].iloc[:5].isna().all()
    assert np.isclose(out["A"].iloc[5], (1 + 2 + 3 + 4 + 5) / 50)      # session 5 sees sessions 0-4, not itself
    assert np.isclose(out["A"].iloc[6], (2 + 3 + 4 + 5 + 6) / 50)


def test_news_flag_window_and_unknown_names():
    idx = sessions(20)
    filings = pd.DataFrame({"symbol": ["A"], "acceptance_utc": ["2020-01-08 16:00:00+00:00"]})   # 11:00 New York on session 4
    out = sh.news_matrix(filings, idx, ["A", "B"])
    assert out["A"].iloc[4:9].tolist() == [True] * 5 and not out["A"].iloc[3] and not out["A"].iloc[9]
    assert out["B"].isna().all()


def test_news_after_snapshot_waits_for_next_session():
    idx = sessions(20)
    filings = pd.DataFrame({"symbol": ["A"], "acceptance_utc": ["2020-01-08 20:55:00+00:00"]})   # 15:55 New York on session 4
    out = sh.news_matrix(filings, idx, ["A"])
    assert not out["A"].iloc[4] and out["A"].iloc[5]


def test_attention_ratio_excludes_decision_day():
    idx = sessions(80)
    views = pd.DataFrame({"A": np.ones(80)}, index=idx)
    views.iloc[70] = 1000.0
    r = sh.attention_matrix(views, idx)
    assert np.isclose(r["A"].iloc[70], 1.0)       # the spike day itself is not used
    assert r["A"].iloc[71] > 100


def test_filtered_targets_rank_only_scored_names():
    idx = sessions(10)
    close = pd.DataFrame(100.0, index=idx, columns=list("ABCDEFGHIJ"))
    scores = pd.DataFrame(np.nan, idx, close.columns)
    scores.iloc[:, :3] = [3.0, 2.0, 1.0]
    sh.FIRST_DECISION = str(idx[0].date())
    rule = sh.PARENT_RULE
    targets, detail = sh.generate_targets(rule, close, scores, [idx[0]], lambda d: [frozenset(close.columns)] * len(d))
    assert detail[0]["ranked"] == ["A", "B", "C"] and detail[0]["picks"] == ["A"]


def test_cluster_t_and_weekday_scores():
    x = np.array([0.01, 0.02, 0.03, 0.04])
    assert ev.cluster_t(x, np.array(["w1", "w1", "w2", "w2"])) > 0
    idx = pd.bdate_range("2020-01-06", periods=150)          # starts on a Monday
    close = pd.DataFrame({"A": 100.0, "B": 100.0}, index=idx)
    bump = np.where(idx.weekday == 2, 1.01, 1.0)              # A jumps 1% every Wednesday
    close["A"] = 100.0 * np.cumprod(bump)
    s = wd.weekday_scores(close)
    tuesday = idx[(idx.weekday == 1)][-1]
    assert s.loc[tuesday, "A"] > s.loc[tuesday, "B"]           # tuesday close predicts wednesday's return
    thursday = idx[(idx.weekday == 3)][-1]
    assert abs(s.loc[thursday, "A"] - s.loc[thursday, "B"]) < 1e-12   # friday: A did nothing special
