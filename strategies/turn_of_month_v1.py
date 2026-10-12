"""Hypothesis 11: long over the last trading day of each month and the first three of the next.

Uses the scheduled NYSE calendar only. See research/seasonality-analyst-2026-10-12.md.
Not a recommendation.
"""

import pandas as pd

from core.market_calendar import next_trading_day, trading_days

VERSION = 1
PARAMS = {"days_before": 1, "days_after": 3}


def in_window_days(start, end, days_before=PARAMS["days_before"], days_after=PARAMS["days_after"]):
    days = pd.Series(trading_days(start, end))
    month = days.dt.to_period("M")
    from_start = days.groupby(month).cumcount() + 1                 # +1, +2, ...
    from_end = days.groupby(month).cumcount(ascending=False) + 1    # 1 = last day (day -1)
    return pd.DatetimeIndex(days[(from_start <= days_after) | (from_end <= days_before)])


def generate_signals(bars):
    nxt = next_trading_day(bars.index)
    window = in_window_days(bars.index.min() - pd.Timedelta(days=45), nxt.max() + pd.Timedelta(days=45))
    return pd.Series(nxt.isin(window).astype(float), index=bars.index)
