"""Scheduled NYSE trading calendar built from fixed holiday rules, not from gaps in price data.

Unscheduled closures (e.g. 2018-12-05, 2025-01-09) are deliberately not holidays: they were not
known in advance, so a calendar rule that used them would be peeking.
"""

import pandas as pd
from pandas.tseries.holiday import (AbstractHolidayCalendar, GoodFriday, Holiday, USLaborDay,
                                    USMartinLutherKingJr, USMemorialDay, USPresidentsDay,
                                    USThanksgivingDay, nearest_workday, sunday_to_monday)


class NYSEHolidayCalendar(AbstractHolidayCalendar):
    rules = [
        # NYSE does not observe New Year's Day on the prior Friday when Jan 1 is a Saturday.
        Holiday("New Year's Day", month=1, day=1, observance=sunday_to_monday),
        USMartinLutherKingJr,
        USPresidentsDay,
        GoodFriday,
        USMemorialDay,
        Holiday("Juneteenth", month=6, day=19, start_date="2022-01-01", observance=nearest_workday),
        Holiday("Independence Day", month=7, day=4, observance=nearest_workday),
        USLaborDay,
        USThanksgivingDay,
        Holiday("Christmas", month=12, day=25, observance=nearest_workday),
    ]


def holidays(start, end) -> pd.DatetimeIndex:
    return NYSEHolidayCalendar().holidays(start, end)


def trading_days(start, end) -> pd.DatetimeIndex:
    return pd.bdate_range(start, end).difference(holidays(start, end))


def next_trading_day(dates: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """The scheduled trading day after each date (known in advance from the calendar)."""
    days = trading_days(dates.min() - pd.Timedelta(days=10), dates.max() + pd.Timedelta(days=20))
    return days[days.searchsorted(dates, side="right")]


def sessions_to_month_end(index: pd.DatetimeIndex) -> pd.Series:
    """For each date, the number of scheduled sessions after it in its month (0 on the last one)."""
    days = pd.Series(trading_days(index.min() - pd.Timedelta(days=10), index.max() + pd.Timedelta(days=45)))
    remaining = days.groupby(days.dt.to_period("M")).cumcount(ascending=False)
    return pd.Series(remaining.to_numpy(), index=pd.DatetimeIndex(days)).reindex(index)
