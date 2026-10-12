"""Hypothesis 27: overnight-component trend filter.

T_t = 126-day sum of overnight log returns ON = ln(open_t / close_{t-1}). Weight 1 if T > 0, else 0;
weight 1 until T exists (first 126 rows). `component="close"` runs the memo's close-to-close
control (same rule on ln(close_t / close_{t-1})); it is diagnostic only and is not scored.
See research/r3-overnight-signal-analyst-2026-10-12.md. Not a recommendation.
"""

import numpy as np
import pandas as pd

VERSION = 1
PARAMS = {"window": 126, "component": "overnight"}


def generate_signals(bars, window=PARAMS["window"], component=PARAMS["component"]):
    if component == "overnight":
        returns = np.log(bars["open"] / bars["close"].shift(1))
    elif component == "close":
        returns = np.log(bars["close"] / bars["close"].shift(1))
    else:
        raise ValueError("component must be 'overnight' or 'close'")
    trend = returns.rolling(window).sum()
    return pd.Series(np.where(trend.isna() | (trend > 0), 1.0, 0.0), index=bars.index)
