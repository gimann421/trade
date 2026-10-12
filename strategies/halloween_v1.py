"""Hypothesis 29: Halloween window, long from the last October close to the last April close.

Weight 1 iff the month of the next scheduled trading day (core.market_calendar) is November
through April, else 0; it uses the calendar only.
See research/r3-calendar-event-analyst-2026-10-12.md. Not a recommendation.
"""

import pandas as pd

from core.market_calendar import next_trading_day

VERSION = 1
PARAMS = {"months": (11, 12, 1, 2, 3, 4)}


def generate_signals(bars, months=PARAMS["months"]):
    return pd.Series(next_trading_day(bars.index).month.isin(months).astype(float), index=bars.index)
