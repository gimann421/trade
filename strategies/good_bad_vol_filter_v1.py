"""Hypothesis 20: good-vol / bad-vol filter.

vol20 = 20-day std of daily log returns, median252 = its trailing 252-day median (including
today), DS20 = share of the 20-day sum of squared log returns that comes from down days.
Weight 1, but 0 while vol20 > median252 and DS20 >= 0.70; back to 1 when vol20 <= median252
or DS20 <= 0.50. Weight 1 during the warm-up (until the median exists).
See research/r2-volatility-regime-analyst-2026-10-12.md. Not a recommendation.
"""

import numpy as np
import pandas as pd

VERSION = 1
PARAMS = {"vol_window": 20, "median_window": 252, "exit_share": 0.70, "reenter_share": 0.50}


def generate_signals(bars, vol_window=PARAMS["vol_window"], median_window=PARAMS["median_window"],
                     exit_share=PARAMS["exit_share"], reenter_share=PARAMS["reenter_share"]):
    log_ret = np.log(bars["close"]).diff()
    vol = log_ret.rolling(vol_window).std()
    median = vol.rolling(median_window).median()
    squared = log_ret ** 2
    down_share = squared.where(log_ret < 0, 0.0).rolling(vol_window).sum() / squared.rolling(vol_window).sum()
    weights, held = [], True
    for v, m, share in zip(vol, median, down_share):
        if not (np.isnan(m) or np.isnan(share)):
            if held and v > m and share >= exit_share:
                held = False
            elif not held and (v <= m or share <= reenter_share):
                held = True
        weights.append(1.0 if held else 0.0)
    return pd.Series(weights, index=bars.index)
