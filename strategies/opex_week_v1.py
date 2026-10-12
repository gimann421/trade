"""Hypothesis 13: long only during the Monday-Friday week containing each month's third Friday.

See research/seasonality-analyst-2026-10-12.md. Not a recommendation.
"""

import pandas as pd

from core.market_calendar import next_trading_day

VERSION = 1
PARAMS = {}


def generate_signals(bars):
    nxt = next_trading_day(bars.index)
    first = nxt.to_period("M").to_timestamp()
    third_friday = first + pd.to_timedelta((4 - first.weekday) % 7 + 14, unit="D")
    monday = third_friday - pd.Timedelta(days=4)
    in_week = (nxt >= monday) & (nxt <= third_friday)
    return pd.Series(in_week.astype(float), index=bars.index)
