"""Hypotheses 121-124: state and filter variants of the 3-session band reversal rule (rev5_h3_band40_s).

Timing as in v2-v4: the decision-day price is the 15:45 snapshot, the fill is the official close, every 3rd session
from the close of 2016-12-30, book 10%, keep a held name while it is in the top 40%. Variants:
  vixgate   active book (the band book) only when the previous session's VIX close is above the median of the
            previous 252 closes; otherwise the equal-weight of all priced members
  vixscale  share s = clip(VIX / median - 0.5, 0, 1) in the band book, the rest in the equal-weight of all priced members
  rev5r     score = minus the 5-day return after removing 60-session market beta (estimated ending 5 sessions
            before the decision day), then demeaned within its SIC two-digit group
  rev5v     rev5, but names whose 5-session volume exceeds 1.5 times their prior 60-session norm are not ranked
See research/r12-vix-residual-volume-fomc-2026-10-15.md. Not a recommendation.
"""

import numpy as np
import pandas as pd

VERSION = 5
FIRST_DECISION = "2016-12-30"
CASH = "BIL"
MIN_GROUP = 5
VOLUME_BASE = 60
VOLUME_LIMIT = 1.5
BETA_DAYS, BETA_MIN, BETA_LAG = 60, 40, 5

# id, signal, vix mode
GRID = [("rev5_h3_band40_vixgate_s", "rev5", "gate"), ("rev5_h3_band40_vixscale_s", "rev5", "scale"),
        ("rev5r_h3_band40_s", "rev5r", None), ("rev5v_h3_band40_s", "rev5v", None)]
PARENT = ("rev5_h3_band40_s", "rev5", None)


def _rule(rid, signal, vix, role):
    return {"id": rid, "signal": signal, "vix": vix, "hold": 3, "kind": "band", "band": 0.4, "fraction": 0.1,
            "role": role, "family": "stock"}


RULES = [_rule(*g, "test") for g in GRID]
PARENT_RULE = _rule(*PARENT, "parent")


def vix_share(vix: pd.Series, index: pd.DatetimeIndex, mode: str) -> pd.Series:
    """Active share per session from the previous session's VIX close and the median of the 252 closes ending then."""
    v = vix.reindex(vix.index.union(index)).ffill().reindex(index)
    prev = v.shift(1)
    median = prev.rolling(252, min_periods=200).median()
    ratio = prev / median
    if mode == "gate":
        return (ratio > 1.0).astype(float).where(ratio.notna())
    return (ratio - 0.5).clip(0.0, 1.0)


def rev5_matrix(close: pd.DataFrame, snap45: pd.DataFrame) -> pd.DataFrame:
    return -(snap45.reindex(index=close.index, columns=close.columns) / close.shift(5) - 1)


def residual_matrix(close: pd.DataFrame, snap45: pd.DataFrame) -> pd.DataFrame:
    """Minus the 5-day return net of beta times the cross-sectional mean 5-day return (stocks only)."""
    snap = snap45.reindex(index=close.index, columns=close.columns)
    daily = close.pct_change(fill_method=None)
    market = daily.mean(axis=1)
    mean_xy = (daily.mul(market, axis=0)).rolling(BETA_DAYS, min_periods=BETA_MIN).mean()
    cov = mean_xy - daily.rolling(BETA_DAYS, min_periods=BETA_MIN).mean().mul(market.rolling(BETA_DAYS, min_periods=BETA_MIN).mean(), axis=0)
    beta = cov.div(market.rolling(BETA_DAYS, min_periods=BETA_MIN).var(ddof=0), axis=0).shift(BETA_LAG)
    r5 = snap / close.shift(5) - 1
    resid = r5 - beta.mul(r5.mean(axis=1), axis=0)
    return -resid


def volume_ratio(vol: pd.DataFrame, days: int = 5) -> pd.DataFrame:
    return vol.rolling(days).mean() / vol.shift(days).rolling(VOLUME_BASE).mean()


def neutralize(row: pd.Series, groups: pd.Series) -> pd.Series:
    g = groups.reindex(row.index)
    sizes = g.map(g.value_counts())
    mean_group = row.groupby(g).transform("mean")
    return row - mean_group.where(g.notna() & (sizes >= MIN_GROUP), row.mean())


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


def generate_targets(rule: dict, close: pd.DataFrame, scores: pd.DataFrame, decisions, members_on_fn,
                     share: pd.Series | None = None, groups: pd.Series | None = None,
                     ratio: pd.DataFrame | None = None):
    index = close.index
    strategy = pd.DataFrame(np.nan, index, close.columns)
    decisions = [d for d in pd.DatetimeIndex(decisions) if d in index and d >= pd.Timestamp(FIRST_DECISION)]
    detail, held = [], []
    for date, candidates in zip(decisions, members_on_fn(decisions)):
        priced = [t for t in sorted(candidates) if t in close.columns and pd.notna(close.at[date, t])]
        row = scores.loc[date, priced].dropna() if priced else pd.Series(dtype=float)
        if rule["signal"] == "rev5v":
            r = ratio.loc[date, row.index]
            row = row[(r <= VOLUME_LIMIT).reindex(row.index).fillna(False)]
        elif rule["signal"] == "rev5r" and len(row):
            row = neutralize(row, groups)
        ranked = list(row.index)
        picks = select(rule, row, held)
        s = 1.0
        if rule["vix"]:
            s = share.get(date, np.nan)
            s = 1.0 if pd.isna(s) else float(s)       # no VIX history yet: behave as the parent
        strategy.loc[date] = 0.0
        if picks:
            strategy.loc[date, picks] = s / len(picks)
        if s < 1.0 and priced:
            strategy.loc[date, priced] = strategy.loc[date, priced] + (1.0 - s) / len(priced)
        held = picks
        detail.append({"date": date, "priced": priced, "ranked": ranked, "picks": picks, "share": s})
    return strategy, detail
