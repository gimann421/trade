"""Hypothesis 4: long after a 63-day closing high, flat after a close below the prior 21-day low.

Flat until the first 63-day high. See research/trend-analyst-2026-10-12.md. Not a recommendation.
"""

import pandas as pd

VERSION = 1
PARAMS = {"entry": 63, "exit": 21}


def generate_signals(bars, entry=PARAMS["entry"], exit=PARAMS["exit"]):
    close = bars["close"]
    new_high = close >= close.rolling(entry).max()
    breaks_low = close < close.shift(1).rolling(exit).min()
    weights, held = [], False
    for up, down in zip(new_high, breaks_low):
        if held and down:
            held = False
        elif not held and up:
            held = True
        weights.append(1.0 if held else 0.0)
    return pd.Series(weights, index=bars.index)
