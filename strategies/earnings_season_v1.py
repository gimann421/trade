"""Hypothesis 30: earnings-season window, trading day 11 to month-end in January, April, July, October.

Weight 1 iff the next scheduled trading day is trading day number >= 11 of its month and the month
is in {1, 4, 7, 10}: enter at the close of day 10, exit at the month's last close. It uses the
calendar only. See research/r3-calendar-event-analyst-2026-10-12.md. Not a recommendation.
"""

import pandas as pd

from core.market_calendar import next_trading_day, trading_days

VERSION = 1
PARAMS = {"months": (1, 4, 7, 10), "first_day": 11}


def generate_signals(bars, months=PARAMS["months"], first_day=PARAMS["first_day"]):
    nxt = next_trading_day(bars.index)
    days = pd.Series(trading_days(bars.index.min() - pd.Timedelta(days=60), nxt.max() + pd.Timedelta(days=60)))
    number = pd.Series(days.groupby(days.dt.to_period("M")).cumcount().to_numpy() + 1, index=pd.DatetimeIndex(days))
    in_window = nxt.month.isin(months) & (number.reindex(nxt).to_numpy() >= first_day)
    return pd.Series(in_window.astype(float), index=bars.index)
