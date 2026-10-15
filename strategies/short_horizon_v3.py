"""Hypotheses 103-111: neighbours of the round-9 band rule (strategies/short_horizon_v2.py) with the band, book size,
hold and signal window as parameters of each rule. Same timing: the 15:45 price on the decision day, fill at the close.

Original v2 docstring:

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

VERSION = 3
FIRST_DECISION = "2016-12-30"
CASH = "BIL"
FRACTION = 0.1
BAND = 0.3
VOLUME_BASE = 60

# id, signal, hold, kind, band, fraction
BASE = ("rev5_h2_band_s", "rev5", 2, "band", 0.3, 0.1)
GRID = [BASE,
        ("rev5_h2_band20_s", "rev5", 2, "band", 0.2, 0.1), ("rev5_h2_band40_s", "rev5", 2, "band", 0.4, 0.1),
        ("rev5_h3_band_s", "rev5", 3, "band", 0.3, 0.1),
        ("rev5_h2_band_b5_s", "rev5", 2, "band", 0.3, 0.05), ("rev5_h2_band_b15_s", "rev5", 2, "band", 0.3, 0.15),
        ("rev3_h2_band_s", "rev3", 2, "band", 0.3, 0.1), ("rev7_h2_band_s", "rev7", 2, "band", 0.3, 0.1),
        ("rev5_h3_band20_s", "rev5", 3, "band", 0.2, 0.1), ("rev5_h3_band40_s", "rev5", 3, "band", 0.4, 0.1)]
WINDOW = {"rev3": 3, "rev5": 5, "rev7": 7, "id5": 5, "rev1": 1}


def build_rules() -> list[dict]:
    return [{"id": rid, "signal": sig, "hold": hold, "kind": kind, "band": band, "fraction": fraction, "family": "stock"}
            for rid, sig, hold, kind, band, fraction in GRID]


RULES = build_rules()


def score_matrix(name: str, open_: pd.DataFrame, close: pd.DataFrame, snap: pd.DataFrame | None) -> pd.DataFrame:
    """Score per date and ticker (higher is better). With snap, the decision-day price is the snapshot
    (NaN snapshot -> the name is not ranked that day); with snap=None it is the official close (round-8 timing)."""
    last = close if snap is None else snap.reindex(index=close.index, columns=close.columns)
    if name in ("rev1", "rev3", "rev5", "rev7"):
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


def select(rule: dict, row: pd.Series, held: list[str]) -> list[str]:
    """Names to hold given the ranked scores `row` (NaN already dropped, and low-volume names removed for lv)
    and the names held after the previous decision."""
    n = max(1, int(round(rule.get("fraction", FRACTION) * len(row)))) if len(row) else 0
    if not n:
        return []
    if rule["kind"] == "band":
        order = _top(row, len(row))
        cutoff = set(order[:max(n, int(round(rule.get("band", BAND) * len(row))))])
        keep = [t for t in held if t in cutoff]
        fill = [t for t in order if t not in keep][:max(0, n - len(keep))]
        return sorted(keep + fill)
    return _top(row, n)


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
        picks = select(rule, row, held)
        strategy.loc[date] = 0.0
        if picks:
            strategy.loc[date, picks] = 1.0 / len(picks)
        held = picks
        detail.append({"date": date, "priced": priced, "ranked": ranked, "picks": picks})
    return strategy, detail
