"""Hypothesis 8: go flat when 10-day realized vol exceeds 1.5x 100-day; back in when the ratio is below 1.0.

Long during warm-up. See research/volatility-analyst-2026-10-12.md. Not a recommendation.
"""

import numpy as np
import pandas as pd

VERSION = 1
PARAMS = {"short": 10, "long": 100, "exit_ratio": 1.5, "reenter_ratio": 1.0}


def generate_signals(bars, short=PARAMS["short"], long=PARAMS["long"],
                     exit_ratio=PARAMS["exit_ratio"], reenter_ratio=PARAMS["reenter_ratio"]):
    log_ret = np.log(bars["close"]).diff()
    ratio = log_ret.rolling(short).std() / log_ret.rolling(long).std()
    weights, held = [], True
    for r in ratio:
        if held and r > exit_ratio:
            held = False
        elif not held and r < reenter_ratio:
            held = True
        weights.append(1.0 if held else 0.0)
    return pd.Series(weights, index=bars.index)
