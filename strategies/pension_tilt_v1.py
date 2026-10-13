"""Hypothesis 32: pension rebalancing tilt in the last week of the month.

C_t = base (1 + R_e) / (base (1 + R_e) + (1 - base)(1 + R_b)) - base, with R_e and R_b the equity and
bond total returns since the previous month's last close. On signal days T-5..T-1 (T = last
scheduled trading day of the month) with |C_t| >= 0.33 pp, hold equity = base - tilt x sign(C_t),
bond = 1 - equity. A below-threshold signal day returns to base weights if the previous day was
tilted, otherwise does not trade. Base weights (60/40) on the first bar and at every month-end.
See research/r4-month-end-flows-2026-10-13.md. Not a recommendation.
"""

import numpy as np
import pandas as pd

from core.market_calendar import sessions_to_month_end

VERSION = 1
PARAMS = {"base": 0.6, "tilt": 0.2, "threshold": 0.0033, "signal_days": (1, 2, 3, 4, 5)}
UNIVERSES = {
    "vti_iei": {"equity": "VTI", "bond": "IEI"},
    "vti_vgit": {"equity": "VTI", "bond": "VGIT"},
    "vea_iei": {"equity": "VEA", "bond": "IEI"},
}


def generate_weights(bars, equity="VTI", bond="IEI", base=PARAMS["base"], tilt=PARAMS["tilt"],
                     threshold=PARAMS["threshold"], signal_days=PARAMS["signal_days"]):
    close = pd.DataFrame({s: b["close"] for s, b in bars.items()})
    columns = list(close.columns)
    remaining = sessions_to_month_end(close.index).to_numpy()
    e_close, b_close = close[equity].to_numpy(), close[bond].to_numpy()

    def row(w_equity):
        r = np.zeros(len(columns))
        r[columns.index(equity)], r[columns.index(bond)] = w_equity, 1.0 - w_equity
        return r

    out = np.full(close.shape, np.nan)
    out[0] = row(base)
    anchor, tilted = None, False
    for i in range(len(close)):
        if remaining[i] in signal_days and anchor is not None:
            r_e, r_b = e_close[i] / anchor[0] - 1, b_close[i] / anchor[1] - 1
            drift = base * (1 + r_e) / (base * (1 + r_e) + (1 - base) * (1 + r_b)) - base
            if abs(drift) >= threshold:
                out[i], tilted = row(base - tilt * np.sign(drift)), True
            elif tilted:
                out[i], tilted = row(base), False
        if remaining[i] == 0:
            out[i], tilted = row(base), False
            anchor = (e_close[i], b_close[i])
    return pd.DataFrame(out, close.index, columns)
