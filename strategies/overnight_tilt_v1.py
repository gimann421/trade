"""Hypothesis 26: overnight-strength tilt, halve exposure after a top-quintile 20-day overnight run.

ON_t = ln(open_t / close_{t-1}); S_t = 20-day sum of ON; P_t = fraction of the last 252 values of
S (including S_t) that are <= S_t. Weight 1; 0.5 once P >= 0.80; back to 1 when P < 0.60; otherwise
keep the previous weight. Weight 1 until P exists (252 valid S values, so from about row 271).
See research/r3-overnight-signal-analyst-2026-10-12.md. Not a recommendation.
"""

import numpy as np
import pandas as pd

VERSION = 1
PARAMS = {"sum_window": 20, "rank_window": 252, "enter": 0.80, "exit": 0.60, "reduced": 0.5}


def generate_signals(bars, sum_window=PARAMS["sum_window"], rank_window=PARAMS["rank_window"],
                     enter=PARAMS["enter"], exit=PARAMS["exit"], reduced=PARAMS["reduced"]):
    overnight = np.log(bars["open"] / bars["close"].shift(1))
    strength = overnight.rolling(sum_window).sum()
    rank = strength.rolling(rank_window).apply(lambda x: (x <= x[-1]).mean(), raw=True)
    weights, weight = [], 1.0
    for p in rank:
        if not np.isnan(p):
            if p >= enter:
                weight = reduced
            elif p < exit:
                weight = 1.0
        weights.append(weight)
    return pd.Series(weights, index=bars.index)
