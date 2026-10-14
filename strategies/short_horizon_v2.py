"""Hypotheses 94-102: short-horizon stock rules read at 15:45 and filled at the close, with bands and a volume filter.

Every h trading days (h = 2 or 5) from the close of 2016-12-30, rank the priced point-in-time S&P 500 members on a
signal that uses the 15:45 price of the decision day (or the 15:30 price, for the noise check) and official closes
and opens before it, then trade at the official close of the decision day. Signals as in short_horizon_v1:
  rev1  minus the 1-day return       rev5  minus the 5-day return       id5  minus the sum of 5 intraday log returns
Selection kinds:
  plain  top decile of ranked names, equal weight
  band   keep a held name while its rank is in the top 30%; fill empty slots from the top until the book holds
         as many names as the plain decile would
  lv     as plain, but only among names whose volume over the signal window is at or below its prior 60-session
         norm (volume measured to 15:45 on every day)
See research/r9-executable-short-horizon-2026-10-14.md. Not a recommendation.
"""

import numpy as np
import pandas as pd

VERSION = 2
FIRST_DECISION = "2016-12-30"
CASH = "BIL"
FRACTION = 0.1
BAND = 0.3
VOLUME_BASE = 60

# (id suffix, signal, hold, kind)
GRID = [("rev1_h2_s", "rev1", 2, "plain"), ("rev5_h2_s", "rev5", 2, "plain"),
        ("id5_h2_s", "id5", 2, "plain"), ("rev1_h5_s", "rev1", 5, "plain"),
        ("rev1_h2_band_s", "rev1", 2, "band"), ("rev5_h2_band_s", "rev5", 2, "band"),
        ("id5_h2_band_s", "id5", 2, "band"),
        ("rev1_h2_lv_s", "rev1", 2, "lv"), ("rev5_h2_lv_s", "rev5", 2, "lv")]
WINDOW = {"rev1": 1, "rev5": 5, "id5": 5}


def build_rules() -> list[dict]:
    return [{"id": rid, "signal": sig, "hold": hold, "kind": kind, "family": "stock"} for rid, sig, hold, kind in GRID]


RULES = build_rules()


def score_matrix(name: str, open_: pd.DataFrame, close: pd.DataFrame, snap: pd.DataFrame | None) -> pd.DataFrame:
    """Score per date and ticker (higher is better). With snap, the decision-day price is the snapshot
    (NaN snapshot -> the name is not ranked that day); with snap=None it is the official close (round-8 timing)."""
    last = close if snap is None else snap.reindex(index=close.index, columns=close.columns)
    if name in ("rev1", "rev5"):
        k = WINDOW[name]
        return -(last / close.shift(k) - 1)
    if name == "id5":
        past = np.log(close / open_).shift(1).rolling(4).sum()
        return -(past + np.log(last / open_))
    raise ValueError(f"unknown signal {name}")


def volume_ratio(vol: pd.DataFrame, days: int) -> pd.DataFrame:
    """Mean volume over the last `days` sessions over the mean of the VOLUME_BASE sessions before them."""
    return vol.rolling(days).mean() / vol.shift(days).rolling(VOLUME_BASE).mean()


def decision_dates(index: pd.DatetimeIndex, hold: int) -> list:
    start = index.searchsorted(pd.Timestamp(FIRST_DECISION))
    return list(index[start::hold])


def _top(series: pd.Series, n: int) -> list[str]:
    return [t for t, _ in sorted(series.items(), key=lambda kv: (-kv[1], kv[0]))[:n]]


def generate_targets(rule: dict, close: pd.DataFrame, scores: pd.DataFrame, ratio: pd.DataFrame | None,
                     decisions, members_on_fn):
    """Strategy targets (NaN rows = no trade) and per-rebalance detail (date, priced, ranked, picks)."""
    index = close.index
    strategy = pd.DataFrame(np.nan, index, close.columns)
    decisions = [d for d in pd.DatetimeIndex(decisions) if d in index and d >= pd.Timestamp(FIRST_DECISION)]
    detail, held = [], []
    for date, candidates in zip(decisions, members_on_fn(decisions)):
        priced = [t for t in sorted(candidates) if t in close.columns and pd.notna(close.at[date, t])]
        row = scores.loc[date, priced].dropna() if priced else pd.Series(dtype=float)
        if rule["kind"] == "lv":
            r = ratio.loc[date, row.index]
            row = row[(r <= 1.0).reindex(row.index).fillna(False)]
        ranked = list(row.index)
        n = max(1, int(round(FRACTION * len(row)))) if len(row) else 0
        if rule["kind"] == "band" and n:
            order = _top(row, len(row))
            cutoff = set(order[:max(n, int(round(BAND * len(row))))])
            keep = [t for t in held if t in cutoff]
            fill = [t for t in order if t not in keep][:max(0, n - len(keep))]
            picks = sorted(keep + fill)
        else:
            picks = _top(row, n) if n else []
        strategy.loc[date] = 0.0
        if picks:
            strategy.loc[date, picks] = 1.0 / len(picks)
        held = picks
        detail.append({"date": date, "priced": priced, "ranked": ranked, "picks": picks})
    return strategy, detail
