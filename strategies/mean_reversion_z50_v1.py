"""Hypothesis 18: multi-week 50-day mean reversion with no trend filter.

z50 = (close - SMA50) / std50 (population std, as in hypothesis 17). Long when z50 < -1.5,
held until the first close with z50 >= 0 or 30 trading days, whichever comes first. One trade
at a time: triggers while in a trade are ignored, and the exit bar itself stays flat.
See research/r2-mean-reversion-analyst-2026-10-12.md. Not a recommendation.
"""

import numpy as np
import pandas as pd

VERSION = 1
PARAMS = {"window": 50, "enter_z": -1.5, "exit_z": 0.0, "max_hold": 30}


def generate_signals(bars, window=PARAMS["window"], enter_z=PARAMS["enter_z"],
                     exit_z=PARAMS["exit_z"], max_hold=PARAMS["max_hold"]):
    close = bars["close"]
    z = (close - close.rolling(window).mean()) / close.rolling(window).std(ddof=0)
    weights, held, days = [], False, 0
    for value in z:
        if held:
            days += 1
            if (not np.isnan(value) and value >= exit_z) or days >= max_hold:
                held = False
        elif not np.isnan(value) and value < enter_z:
            held, days = True, 0
        weights.append(1.0 if held else 0.0)
    return pd.Series(weights, index=bars.index)
