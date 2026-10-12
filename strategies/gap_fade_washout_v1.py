"""Hypothesis 28: gap-up-faded intraday washout, 3-day long.

ON_t = ln(open_t / close_{t-1}), ID_t = ln(close_t / open_t), z_t = ID_t / sample std of the 60
values ID_{t-60..t-1} (excludes day t). Trigger at day t's close when z_t <= -2.0 and ON_t > 0:
weight 1 on signal days t, t+1, t+2, so the position is held over returns t+1..t+3. Triggers
during a hold are ignored and the exit bar stays flat. Weight 0 in the first 61 rows.
See research/r3-overnight-signal-analyst-2026-10-12.md. Not a recommendation.
"""

import numpy as np
import pandas as pd

VERSION = 1
PARAMS = {"std_window": 60, "z_max": -2.0, "hold": 3, "warmup": 61}


def generate_signals(bars, std_window=PARAMS["std_window"], z_max=PARAMS["z_max"],
                     hold=PARAMS["hold"], warmup=PARAMS["warmup"]):
    overnight = np.log(bars["open"] / bars["close"].shift(1))
    intraday = np.log(bars["close"] / bars["open"])
    z = intraday / intraday.shift(1).rolling(std_window).std()
    trigger = ((z <= z_max) & (overnight > 0)).to_numpy()
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
