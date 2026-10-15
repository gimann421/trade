"""Hypotheses 126-128: eligibility filters on the 3-session band reversal rule (rev5_h3_band40_s).

Timing as in v2-v5: the decision-day price is the 15:45 snapshot, the fill is the official close, every 3rd session from
the close of 2016-12-30, book 10% of the ranked names, keep a held name while it is in the top 40%. A filter only
changes which names are ranked: a name that fails it, or has no data for it, gets no score.
  sv   short-sale volume over sessions t-5..t-1 divided by total volume, at or below the day's median
  nn   no 8-K accepted between the 16:00 close of session t-5 and 15:45 of session t
  wk   Wikipedia page views of t-5..t-1 over those of t-65..t-6, above the day's median
See research/r13-novel-ideas-2026-10-15.md. Not a recommendation.
"""

import numpy as np
import pandas as pd

VERSION = 6
FIRST_DECISION = "2016-12-30"
CASH = "BIL"
ATTENTION_RECENT, ATTENTION_BASE_START = 5, 65


def _rule(rid, kind, role):
    return {"id": rid, "filter": kind, "hold": 3, "kind": "band", "band": 0.4, "fraction": 0.1, "role": role, "family": "stock"}


RULES = [_rule("rev5sv_h3_band40_s", "sv", "test"), _rule("rev5nn_h3_band40_s", "nn", "test"),
         _rule("rev5wk_h3_band40_s", "wk", "test")]
PARENT_RULE = _rule("rev5_h3_band40_s", None, "parent")


def rev5_matrix(close: pd.DataFrame, snap45: pd.DataFrame) -> pd.DataFrame:
    return -(snap45.reindex(index=close.index, columns=close.columns) / close.shift(5) - 1)


def sv_matrix(short: pd.DataFrame, total: pd.DataFrame, index: pd.DatetimeIndex) -> pd.DataFrame:
    """Short-sale volume share over the five sessions before each session (needs all five)."""
    s = short.reindex(index).rolling(5).sum().shift(1)
    t = total.reindex(index).rolling(5).sum().shift(1)
    return (s / t.where(t > 0)).where(t > 0)


def news_matrix(filings: pd.DataFrame, index: pd.DatetimeIndex, columns) -> pd.DataFrame:
    """True where the name has an 8-K accepted after the 16:00 close of session t-5 and by 15:45 of session t.
    Names with no filing history at all stay NaN (not ranked); `filings` has columns symbol, acceptance_utc."""
    ny = "America/New_York"
    t1545 = (index + pd.Timedelta(hours=15, minutes=45)).tz_localize(ny)
    t1600 = (index + pd.Timedelta(hours=16)).tz_localize(ny)
    known = set(filings["symbol"])
    col_pos = {c: k for k, c in enumerate(columns)}
    values = np.full((len(index), len(col_pos)), False, dtype=object)
    for c, k in col_pos.items():
        if c not in known:
            values[:, k] = np.nan
    accepted = pd.to_datetime(filings["acceptance_utc"], utc=True).dt.tz_convert(ny)
    for symbol, a in zip(filings["symbol"], accepted):
        if symbol not in col_pos:
            continue
        j = int(t1545.searchsorted(a, side="left"))           # first session whose 15:45 is at or after the filing
        for t in range(j, min(j + 5, len(index))):
            if t - 5 < 0 or a > t1600[t - 5]:
                values[t, col_pos[symbol]] = True
    return pd.DataFrame(values, index=index, columns=list(columns))


def attention_matrix(views: pd.DataFrame, index: pd.DatetimeIndex) -> pd.DataFrame:
    v = views.reindex(index)
    recent = v.rolling(ATTENTION_RECENT).mean().shift(1)
    base = v.rolling(ATTENTION_BASE_START - ATTENTION_RECENT).mean().shift(ATTENTION_RECENT + 1)
    return recent / base.where(base > 0)


def decision_dates(index: pd.DatetimeIndex, hold: int = 3) -> list:
    return list(index[index.searchsorted(pd.Timestamp(FIRST_DECISION))::hold])


def _top(series: pd.Series, n: int) -> list[str]:
    return [t for t, _ in sorted(series.items(), key=lambda kv: (-kv[1], kv[0]))[:n]]


def select(rule: dict, row: pd.Series, held: list[str]) -> list[str]:
    n = max(1, int(round(rule["fraction"] * len(row)))) if len(row) else 0
    if not n:
        return []
    order = _top(row, len(row))
    cutoff = set(order[:max(n, int(round(rule["band"] * len(row))))])
    keep = [t for t in held if t in cutoff]
    fill = [t for t in order if t not in keep][:max(0, n - len(keep))]
    return sorted(keep + fill)


def generate_targets(rule: dict, close: pd.DataFrame, scores: pd.DataFrame, decisions, members_on_fn):
    """Scores are NaN for names that are not ranked. Same targets as v5 without the VIX share (always 1)."""
    index = close.index
    strategy = pd.DataFrame(np.nan, index, close.columns)
    decisions = [d for d in pd.DatetimeIndex(decisions) if d in index and d >= pd.Timestamp(FIRST_DECISION)]
    detail, held = [], []
    for date, candidates in zip(decisions, members_on_fn(decisions)):
        priced = [t for t in sorted(candidates) if t in close.columns and pd.notna(close.at[date, t])]
        row = scores.loc[date, priced].dropna() if priced else pd.Series(dtype=float)
        picks = select(rule, row, held)
        strategy.loc[date] = 0.0
        if picks:
            strategy.loc[date, picks] = 1.0 / len(picks)
        held = picks
        detail.append({"date": date, "priced": priced, "ranked": list(row.index), "picks": picks, "share": 1.0})
    return strategy, detail
