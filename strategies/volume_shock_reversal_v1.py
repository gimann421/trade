"""Hypothesis 19: high-volume liquidity-shock reversal, 5-day hold.

Long at the close where r3 / (sd20 x sqrt(3)) < -1.25 and volume > 1.25 x the mean volume of
the previous 20 days, with r3 = close_t / close_{t-3} - 1 and sd20 the sample std of the 20
daily returns ending at t-1. Held exactly 5 trading days (5 return days); triggers during the
hold are ignored and the exit bar stays flat.
See research/r2-mean-reversion-analyst-2026-10-12.md. Not a recommendation.
"""

import numpy as np
import pandas as pd

VERSION = 1
PARAMS = {"z_max": -1.25, "volume_mult": 1.25, "vol_window": 20, "hold": 5}


def generate_signals(bars, z_max=PARAMS["z_max"], volume_mult=PARAMS["volume_mult"],
                     vol_window=PARAMS["vol_window"], hold=PARAMS["hold"]):
    close, volume = bars["close"], bars["volume"]
    sd = close.pct_change().rolling(vol_window).std().shift(1)
    shock = (close / close.shift(3) - 1) / (sd * np.sqrt(3))
    volume_ratio = volume / volume.rolling(vol_window).mean().shift(1)
    trigger = ((shock < z_max) & (volume_ratio > volume_mult)).to_numpy()
    weights, held, days = [], False, 0
    for fire in trigger:
        if held:
            days += 1
            if days >= hold:
                held = False
        elif fire:
            held, days = True, 0
        weights.append(1.0 if held else 0.0)
    return pd.Series(weights, index=bars.index)
