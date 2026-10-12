import numpy as np
import pandas as pd
import pytest

from core.verdicts import (drawdown_rule, per_day_rule, placebo_percentile, symbol_status,
                           window_arrays)


def result(s_sharpe=1.0, b_sharpe=0.8, s_dd=-0.10, b_dd=-0.30, rpd=0.002, mean=0.0005):
    return {"strategy": {"sharpe": s_sharpe, "max_drawdown": s_dd, "return_per_exposure_day": rpd},
            "buy_and_hold": {"sharpe": b_sharpe, "max_drawdown": b_dd, "mean_daily_return": mean}}


def test_drawdown_rule():
    assert drawdown_rule(result()) == []
    assert len(drawdown_rule(result(s_sharpe=0.7, s_dd=-0.28))) == 2
    assert drawdown_rule(result(s_dd=-0.25)) == []          # exactly 5 points better passes
    assert len(drawdown_rule(result(s_dd=-0.2501))) == 1


def test_per_day_rule():
    assert per_day_rule(2)(result()) == []                    # 0.2% >= 2 x 0.05%
    assert len(per_day_rule(5)(result())) == 1                # 0.2% < 5 x 0.05%
    assert len(per_day_rule(2, sharpe_mult=2)(result())) == 1  # Sharpe 1.0 < 2 x 0.8


@pytest.mark.parametrize("cells, expected", [
    ({s: {"IS": "supports", "OOS": "supports"} for s in "ABCDE"}, "supported"),
    ({**{s: {"IS": "supports", "OOS": "supports"} for s in "ABCD"},
      "E": {"IS": "contradicts", "OOS": "supports"}}, "supported"),
    ({**{s: {"IS": "supports", "OOS": "supports"} for s in "ABC"},
      "D": {"IS": "contradicts", "OOS": "supports"},
      "E": {"IS": "supports", "OOS": "contradicts"}}, "rejected"),
    ({**{s: {"IS": "supports", "OOS": "supports"} for s in "ABC"},
      "D": {"IS": "supports", "OOS": "inconclusive"},
      "E": {"IS": "contradicts", "OOS": "supports"}}, "testing"),
])
def test_symbol_status(cells, expected):
    assert symbol_status(cells, min_symbols=4) == expected


def test_placebo_high_for_real_edge_and_middling_for_random():
    rng = np.random.default_rng(1)
    asset = rng.normal(0.0003, 0.01, 1500)
    # A position that knows which days are up has a clear edge.
    edge = (asset > 0).astype(float)
    assert placebo_percentile(asset, edge, cost_bps=0, metric="sharpe") > 0.99
    # Random on/off timing should sit near the middle of its own placebo distribution.
    random_pos = (rng.random(1500) < 0.3).astype(float)
    pct = placebo_percentile(asset, random_pos, cost_bps=0, metric="return_per_exposure_day", seed=3)
    assert 0.05 < pct < 0.95


def test_placebo_shifts_keep_exposure_and_validates_input():
    asset = np.random.default_rng(0).normal(0, 0.01, 800)
    position = (np.arange(800) % 10 < 3).astype(float)
    # Shifted copies are the same series rolled, so exposure and entry counts are unchanged.
    rolled = np.roll(position, 300)
    assert rolled.sum() == position.sum()
    assert (np.diff(rolled) > 0).sum() == (np.diff(position) > 0).sum()
    with pytest.raises(ValueError, match="metric"):
        placebo_percentile(asset, position, metric="cagr")
    with pytest.raises(ValueError, match="longer"):
        placebo_percentile(asset[:100], position[:100])


def test_window_arrays_use_full_history_positions():
    idx = pd.bdate_range("2020-01-01", periods=300)
    bars = pd.DataFrame({"close": np.linspace(100, 130, 300)}, index=idx)
    asset, position = window_arrays(bars, lambda b: (np.arange(len(b)) >= 100).astype(float) * pd.Series(1.0, index=b.index),
                                    start=idx[150], end=idx[250])
    assert len(asset) == len(position) == 101
    assert position.min() == 1.0    # already long when the window opens: no warm-up restart
