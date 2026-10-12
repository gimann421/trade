"""Hypothesis 14: drawdown-gated SMA200 stepped exit with slow re-entry.

Weight s in {1, 0.5, 0}, starting at 1 (and 1 during indicator warm-up). With c = close,
S = 200-day SMA, H = 252-day rolling max of closes, DD = c / H - 1, updated daily:
  c < S and DD <= -20%            -> 0
  c < S and DD <= -10%            -> min(s, 0.5)
  c > S and s == 0                -> 0.5
  c > S and s == 0.5 and DD > -5% -> 1
  otherwise unchanged.
See research/r2-trend-drawdown-analyst-2026-10-12.md. Not a recommendation.
"""

import numpy as np
import pandas as pd

VERSION = 1
PARAMS = {"sma": 200, "high": 252, "bear": -0.20, "correction": -0.10, "recover": -0.05}


def generate_signals(bars, sma=PARAMS["sma"], high=PARAMS["high"], bear=PARAMS["bear"],
                     correction=PARAMS["correction"], recover=PARAMS["recover"]):
    close = bars["close"]
    mean = close.rolling(sma).mean()
    drawdown = close / close.rolling(high).max() - 1
    weights, s = [], 1.0
    for c, m, dd in zip(close, mean, drawdown):
        if not (np.isnan(m) or np.isnan(dd)):
            if c < m and dd <= bear:
                s = 0.0
            elif c < m and dd <= correction:
                s = min(s, 0.5)
            elif c > m and s == 0.0:
                s = 0.5
            elif c > m and s == 0.5 and dd > recover:
                s = 1.0
        weights.append(s)
    return pd.Series(weights, index=bars.index)
