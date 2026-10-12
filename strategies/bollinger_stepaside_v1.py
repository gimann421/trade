"""Hypothesis 17: Bollinger overbought step-aside.

z = (close - SMA20) / std20 (population std of the same 20 closes). Hold weight 1; step to 0
from the close where z > 2.0 until the first close with z < 0. Weight 1 during warm-up.
See research/r2-mean-reversion-analyst-2026-10-12.md. Not a recommendation.
"""

import numpy as np
import pandas as pd

VERSION = 1
PARAMS = {"window": 20, "enter_z": 2.0, "reenter_z": 0.0}


def generate_signals(bars, window=PARAMS["window"], enter_z=PARAMS["enter_z"],
                     reenter_z=PARAMS["reenter_z"]):
    close = bars["close"]
    z = (close - close.rolling(window).mean()) / close.rolling(window).std(ddof=0)
    weights, held = [], True
    for value in z:
        if not np.isnan(value):
            if held and value > enter_z:
                held = False
            elif not held and value < reenter_z:
                held = True
        weights.append(1.0 if held else 0.0)
    return pd.Series(weights, index=bars.index)
