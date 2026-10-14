"""Hypotheses 71-89: short-horizon long-only stock rules on point-in-time S&P 500 members.

Every h trading days (h = 1, 2, 5 or 10) from the close of 2016-12-30, rank the priced members on a signal
computed from data up to and including that close and hold the top decile (or quintile) equal-weight until
the next decision close. Signals (higher is better):
  rev1   minus the 1-day return              (buy yesterday's losers)
  rev5   minus the 5-day return              rev10  minus the 10-day return
  on5    sum of the last 5 overnight returns (close to next open, summed in logs; buy persistent overnight strength)
  id5    minus the sum of the last 5 intraday returns (open to close; buy persistent intraday weakness)
A name is ranked only if every return in its window exists. See research/r8-short-horizon-2026-10-14.md.
Not a recommendation.
"""

import numpy as np
import pandas as pd

VERSION = 1
FIRST_DECISION = "2016-12-30"
CASH = "BIL"
SIGNALS = ("rev1", "rev5", "rev10", "on5", "id5")
# (signal, hold days, fraction of ranked names held)
GRID = [("rev1", 1, 0.1), ("rev1", 2, 0.1), ("rev1", 5, 0.1),
        ("rev5", 2, 0.1), ("rev5", 5, 0.1), ("rev5", 10, 0.1),
        ("rev10", 5, 0.1), ("rev10", 10, 0.1),
        ("on5", 2, 0.1), ("on5", 5, 0.1), ("on5", 10, 0.1),
        ("id5", 2, 0.1), ("id5", 5, 0.1), ("id5", 10, 0.1),
        ("rev1", 5, 0.2), ("rev5", 5, 0.2), ("rev10", 5, 0.2), ("on5", 5, 0.2), ("id5", 5, 0.2)]


def build_rules() -> list[dict]:
    rules = []
    for signal, hold, fraction in GRID:
        suffix = "_q" if fraction == 0.2 else ""
        rules.append({"id": f"{signal}_h{hold}{suffix}", "family": "stock", "signal": signal, "hold": hold,
                      "fraction": fraction, "trend": False})
    return rules


RULES = build_rules()


def score_matrix(name: str, open_: pd.DataFrame, close: pd.DataFrame) -> pd.DataFrame:
    """Score per date and ticker (higher is better); NaN unless the whole window is observed."""
    if name in ("rev1", "rev5", "rev10"):
        k = {"rev1": 1, "rev5": 5, "rev10": 10}[name]
        return -(close / close.shift(k) - 1)
    if name == "on5":
        overnight = np.log(open_ / close.shift(1))
        return overnight.rolling(5).sum()
    if name == "id5":
        intraday = np.log(close / open_)
        return -intraday.rolling(5).sum()
    raise ValueError(f"unknown signal {name}")


def decision_dates(index: pd.DatetimeIndex, hold: int) -> list:
    """Every `hold`-th session from the first decision close."""
    start = index.searchsorted(pd.Timestamp(FIRST_DECISION))
    return list(index[start::hold])
