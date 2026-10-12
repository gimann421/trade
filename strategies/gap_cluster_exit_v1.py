"""Hypothesis 9: flat while 2+ of the last 10 sessions gapped down by more than 2x the
average absolute overnight gap of the 60 sessions before.

See research/volatility-analyst-2026-10-12.md. Not a recommendation.
"""

VERSION = 1
PARAMS = {"gap_mult": 2.0, "baseline": 60, "window": 10, "min_gaps": 2}


def generate_signals(bars, gap_mult=PARAMS["gap_mult"], baseline=PARAMS["baseline"],
                     window=PARAMS["window"], min_gaps=PARAMS["min_gaps"]):
    gap = bars["open"] / bars["close"].shift(1) - 1
    typical = gap.abs().rolling(baseline).mean().shift(1)  # 60 sessions ending at t-1
    down_gap = (gap < -gap_mult * typical).astype(float)
    return (down_gap.rolling(window, min_periods=1).sum() < min_gaps).astype(float)
