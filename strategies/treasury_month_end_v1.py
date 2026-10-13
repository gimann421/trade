"""Hypothesis 31: month-end Treasury index-extension bid.

Weight 1 at the closes of T-3, T-2 and T-1, where T is the last scheduled NYSE trading day of the
month, so the position earns the returns of T-2, T-1 and T; weight 0 otherwise (cash at 0%).
Dates come from the exchange calendar only.
See research/r4-month-end-flows-2026-10-13.md. Not a recommendation.
"""

import pandas as pd

from core.market_calendar import sessions_to_month_end

VERSION = 1
PARAMS = {"days_before_month_end": (1, 2, 3)}


def generate_signals(bars, days_before_month_end=PARAMS["days_before_month_end"]):
    remaining = sessions_to_month_end(bars.index)
    return pd.Series(remaining.isin(days_before_month_end).astype(float).to_numpy(), index=bars.index)
