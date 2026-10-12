"""Hypothesis 16: CPPI-style drawdown cushion with trend-gated re-risking.

H = 252-day rolling max of closes, floor F = 0.70 H, cushion c = (close - F) / close, target
w* = floor-to-0.25 of min(1, 4c) (0 if c <= 0). Reductions apply immediately; an increase
applies only on days when close > 100-day SMA, otherwise the previous weight is kept.
Weight 1 during warm-up. See research/r2-trend-drawdown-analyst-2026-10-12.md.
Not a recommendation.
"""

import numpy as np
import pandas as pd

VERSION = 1
PARAMS = {"high": 252, "floor": 0.70, "multiplier": 4.0, "gate_sma": 100, "step": 0.25}


def generate_signals(bars, high=PARAMS["high"], floor=PARAMS["floor"],
                     multiplier=PARAMS["multiplier"], gate_sma=PARAMS["gate_sma"],
                     step=PARAMS["step"]):
    close = bars["close"]
    peak = close.rolling(high).max()
    gate = close.rolling(gate_sma).mean()
    weights, previous = [], 1.0
    for c, h, g in zip(close, peak, gate):
        if np.isnan(h):
            w = 1.0
        else:
            cushion = (c - floor * h) / c
            target = 0.0 if cushion <= 0 else float(np.floor(min(1.0, multiplier * cushion) / step) * step)
            if target <= previous:
                w = target
            elif not np.isnan(g) and c > g:
                w = target
            else:
                w = previous
        weights.append(w)
        previous = w
    return pd.Series(weights, index=bars.index)
