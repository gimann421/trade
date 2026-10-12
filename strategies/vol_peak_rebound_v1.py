"""Hypothesis 22: post-spike volatility-peak rebound long, 20-day hold.

vol20 = 20-day std of daily log returns. Long at the close when vol20 was >= its trailing-500-day
90th percentile (including that day) on at least one of the last 10 closes AND today's vol20 <=
0.90 x the maximum vol20 of the last 10 closes. Held exactly 20 trading days; triggers during the
hold are ignored and the exit bar stays flat. Flat for the first 520 bars.
See research/r2-volatility-regime-analyst-2026-10-12.md. Not a recommendation.
"""

import numpy as np
import pandas as pd

VERSION = 1
PARAMS = {"vol_window": 20, "pct_window": 500, "pct": 0.90, "lookback": 10, "peak": 0.90,
          "hold": 20, "warmup": 520}


def generate_signals(bars, vol_window=PARAMS["vol_window"], pct_window=PARAMS["pct_window"],
                     pct=PARAMS["pct"], lookback=PARAMS["lookback"], peak=PARAMS["peak"],
                     hold=PARAMS["hold"], warmup=PARAMS["warmup"]):
    vol = np.log(bars["close"]).diff().rolling(vol_window).std()
    spiked = ((vol >= vol.rolling(pct_window).quantile(pct)).astype(float)
              .rolling(lookback).max() == 1)
    peaked = vol <= peak * vol.rolling(lookback).max()
    trigger = (spiked & peaked).to_numpy()
    weights, held, days = [], False, 0
    for i, fire in enumerate(trigger):
        if i < warmup:
            weights.append(0.0)
            continue
        if held:
            days += 1
            if days >= hold:
                held = False
        elif fire:
            held, days = True, 0
        weights.append(1.0 if held else 0.0)
    return pd.Series(weights, index=bars.index)
