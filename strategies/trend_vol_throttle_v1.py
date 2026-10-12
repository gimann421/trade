"""Hypothesis 15: volatility throttle that only applies in a confirmed downtrend.

Downtrend flag D turns on when close < 200-day SMA and off only when close > 1.02 x SMA
(weight 1 during warm-up). With D off the weight is 1. With D on the weight is
floor-to-0.25 of min(0.5, 0.10 / sigma), sigma = 63-day std of daily log returns x sqrt(252),
so the weight is 0.5, 0.25 or 0 (0 when sigma is above 40%).
See research/r2-trend-drawdown-analyst-2026-10-12.md. Not a recommendation.
"""

import numpy as np
import pandas as pd

VERSION = 1
PARAMS = {"sma": 200, "release": 1.02, "vol_window": 63, "target": 0.10, "cap": 0.5, "step": 0.25}


def generate_signals(bars, sma=PARAMS["sma"], release=PARAMS["release"],
                     vol_window=PARAMS["vol_window"], target=PARAMS["target"],
                     cap=PARAMS["cap"], step=PARAMS["step"]):
    close = bars["close"]
    mean = close.rolling(sma).mean()
    sigma = np.log(close).diff().rolling(vol_window).std() * np.sqrt(252)
    weights, down = [], False
    for c, m, sg in zip(close, mean, sigma):
        if not np.isnan(m):
            if c < m:
                down = True
            elif c > release * m:
                down = False
        if not down:
            weights.append(1.0)
        else:
            raw = cap if (np.isnan(sg) or sg <= 0) else min(cap, target / sg)
            weights.append(float(np.floor(raw / step) * step))
    return pd.Series(weights, index=bars.index)
