"""Hypothesis 6: buy the third consecutive lower close above the 200-day SMA; exit at the first
higher close or after 5 days held. Re-entry needs three new down closes after the exit.

See research/mean-reversion-analyst-2026-10-12.md. Not a recommendation.
"""

import pandas as pd

VERSION = 1
PARAMS = {"streak": 3, "trend": 200, "max_hold": 5}


def generate_signals(bars, streak=PARAMS["streak"], trend=PARAMS["trend"], max_hold=PARAMS["max_hold"]):
    close = bars["close"]
    down = close < close.shift(1)
    up = close > close.shift(1)
    above_trend = close > close.rolling(trend).mean()
    weights, held, days_held, run = [], False, 0, 0
    for is_down, is_up, ok in zip(down, up, above_trend):
        run = run + 1 if is_down else 0
        if held:
            days_held += 1
            if is_up or days_held >= max_hold:
                held, run = False, 0
        elif run >= streak and ok:
            held, days_held = True, 0
        weights.append(1.0 if held else 0.0)
    return pd.Series(weights, index=bars.index)
