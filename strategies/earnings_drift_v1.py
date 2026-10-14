"""Hypotheses 90-93: post-earnings-announcement drift, long only, S&P 500 members.

An earnings release (SEC 8-K Item 2.02) is a reaction session R (see core.edgar.reaction_sessions). The
abnormal reaction AR is the stock's close-to-close return on R minus the equal-weight return of the same set of
stocks. An event qualifies if AR is at or above the q-th percentile of the ARs of all events in the 252
sessions before R (strictly earlier; at least 100 of them). A qualifying name is held from the close of R for
`hold` sessions; weights are equal across active names and the book is BIL when none is active.
See research/r8-short-horizon-2026-10-14.md (Part B). Not a recommendation.
"""

import numpy as np
import pandas as pd

VERSION = 1
HISTORY, MIN_PRIOR = 252, 100
CASH = "BIL"
RULES = [{"id": "pead_q80_h5", "q": 80, "hold": 5}, {"id": "pead_q80_h20", "q": 80, "hold": 20},
         {"id": "pead_q80_h60", "q": 80, "hold": 60}, {"id": "pead_q90_h20", "q": 90, "hold": 20}]


def qualifies(pos: np.ndarray, ar: np.ndarray, q: float) -> np.ndarray:
    """Per event (sorted by session position): AR at or above the q-th percentile of the ARs of events in the
    previous HISTORY sessions, with at least MIN_PRIOR of them."""
    out = np.zeros(len(pos), dtype=bool)
    for i in range(len(pos)):
        lo = np.searchsorted(pos, pos[i] - HISTORY, side="left")
        hi = np.searchsorted(pos, pos[i], side="left")
        if hi - lo >= MIN_PRIOR:
            out[i] = ar[i] >= np.percentile(ar[lo:hi], q)
    return out


def active_matrix(shape: tuple[int, int], pos: np.ndarray, col: np.ndarray, hold: int) -> np.ndarray:
    """True where a qualifying event is active after the close of that session: positions pos..pos+hold-1."""
    active = np.zeros(shape, dtype=bool)
    for p, c in zip(pos, col):
        active[p:min(p + hold, shape[0]), c] = True
    return active


def targets_from_active(active: np.ndarray, index, columns, start: int, cash: str = CASH) -> pd.DataFrame:
    """Rows only on sessions (from position `start`) where the active set changes, and on `start` itself;
    all-NaN elsewhere means no trade. The book is `cash` while nothing is active."""
    targets = pd.DataFrame(np.nan, index, columns)
    cash_col = list(columns).index(cash)
    previous = None
    for t in range(start, active.shape[0]):
        row = active[t]
        if previous is None or (row != previous).any():
            weights = np.zeros(len(columns))
            if row.any():
                weights[:active.shape[1]][row] = 1.0 / row.sum()
            else:
                weights[cash_col] = 1.0
            targets.iloc[t] = weights
        previous = row
    return targets


def hold_returns(close_ff: np.ndarray, market_cum: np.ndarray, pos: np.ndarray, col: np.ndarray, hold: int) -> np.ndarray:
    """h-session abnormal return after R: stock return from the close of R to the close of R+h minus the
    equal-weight return over the same sessions; NaN where R+h is beyond the data."""
    out = np.full(len(pos), np.nan)
    ok = pos + hold < close_ff.shape[0]
    p, c = pos[ok], col[ok]
    out[ok] = (close_ff[p + hold, c] / close_ff[p, c] - 1) - (market_cum[p + hold] / market_cum[p] - 1)
    return out
