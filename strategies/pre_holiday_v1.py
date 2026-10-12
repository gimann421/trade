"""Hypothesis 12: long only over the last trading day before each scheduled NYSE holiday.

See research/seasonality-analyst-2026-10-12.md. Not a recommendation.
"""

import pandas as pd

from core.market_calendar import holidays, next_trading_day

VERSION = 1
PARAMS = {}


def generate_signals(bars):
    nxt = next_trading_day(bars.index)
    hols = holidays(nxt.min(), nxt.max() + pd.Timedelta(days=10))
    next_weekday = nxt + pd.offsets.BDay(1)
    return pd.Series(next_weekday.isin(hols).astype(float), index=bars.index)
