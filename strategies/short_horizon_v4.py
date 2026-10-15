"""Hypotheses 112-120: ideas to cut the cost or sharpen the signal of the band reversal rules of round 10.

Timing as in v2/v3: the decision-day price is the 15:45 snapshot, the fill is the official close. Selection is the
band rule of v3 (book 10%, keep a held name while its rank is inside the band). Variants:
  nt      do not top up: kept names keep their drifted weight, proceeds of the names sold go equally to names bought
  blend   score = z(rev5) + z(id5), z-scores across the ranked names, both signals required
  rev5n   rev5 minus the mean rev5 of the ranked names in the same SIC two-digit group (groups under 5 names, and
          names without a code, use the mean of all ranked names)
  rev5x   rev5, but a name with an earnings reaction session in the 5 sessions ending on the decision day is not ranked
  l15rev / l15mom   minus / plus the return from the 15:30 to the 15:45 price on the decision day
See research/r11-cost-and-signal-ideas-2026-10-15.md. Not a recommendation.
"""

import numpy as np
import pandas as pd

VERSION = 4
FIRST_DECISION = "2016-12-30"
CASH = "BIL"
MIN_GROUP = 5
EXCLUDE_SESSIONS = 5

# id, signal, hold, band, parent (None = a parent rule, run for comparison only), no_top_up
GRID = [("rev5_h3_band40_nt_s", "rev5", 3, 0.4, "rev5_h3_band40_s", True),
        ("rev5_h2_band_nt_s", "rev5", 2, 0.3, "rev5_h2_band_s", True),
        ("blend_h3_band40_s", "blend", 3, 0.4, "rev5_h3_band40_s", False),
        ("rev5n_h3_band40_s", "rev5n", 3, 0.4, "rev5_h3_band40_s", False),
        ("rev5n_h2_band_s", "rev5n", 2, 0.3, "rev5_h2_band_s", False),
        ("rev5x_h3_band40_s", "rev5x", 3, 0.4, "rev5_h3_band40_s", False),
        ("rev5x_h2_band_s", "rev5x", 2, 0.3, "rev5_h2_band_s", False),
        ("l15rev_h2_band_s", "l15rev", 2, 0.3, "l15mom_h2_band_s", False),
        ("l15mom_h2_band_s", "l15mom", 2, 0.3, "l15rev_h2_band_s", False)]
PARENTS = [("rev5_h3_band40_s", "rev5", 3, 0.4, None, False), ("rev5_h2_band_s", "rev5", 2, 0.3, None, False)]


def _rule(rid, signal, hold, band, parent, nt, role):
    return {"id": rid, "signal": signal, "hold": hold, "kind": "band", "band": band, "fraction": 0.1, "parent": parent,
            "no_top_up": nt, "role": role, "family": "stock"}


RULES = [_rule(*g, "test") for g in GRID]
PARENT_RULES = [_rule(*g, "parent") for g in PARENTS]


def exclusion_mask(events: pd.DataFrame, index: pd.DatetimeIndex, columns) -> pd.DataFrame:
    """True where a name's earnings reaction session is among the EXCLUDE_SESSIONS sessions ending that day.
    events: columns symbol and reaction (Timestamp, a session in index)."""
    mask = np.zeros((len(index), len(columns)), dtype=bool)
    col = {c: i for i, c in enumerate(columns)}
    for symbol, reaction in zip(events["symbol"], events["reaction"]):
        if symbol in col and pd.notna(reaction) and reaction in index:
            p = index.get_loc(reaction)
            mask[p:p + EXCLUDE_SESSIONS, col[symbol]] = True
    return pd.DataFrame(mask, index, columns)


def zscore(row: pd.Series) -> pd.Series:
    sd = row.std()
    return (row - row.mean()) / sd if sd and sd > 0 else row * 0.0


def neutralize(row: pd.Series, groups: pd.Series) -> pd.Series:
    """Subtract the group mean of the ranked names; small or unknown groups use the mean of all ranked names."""
    g = groups.reindex(row.index)
    sizes = g.map(g.value_counts())
    mean_group = row.groupby(g).transform("mean")
    return row - mean_group.where(g.notna() & (sizes >= MIN_GROUP), row.mean())


def score_matrix(signal: str, open_, close, snap45, snap30) -> pd.DataFrame:
    """Per-date score (higher is better) for the simple signals; blend and rev5n are completed per date in
    generate_targets."""
    if signal in ("rev5", "rev5n", "rev5x", "blend"):
        return -(snap45.reindex(index=close.index, columns=close.columns) / close.shift(5) - 1)
    if signal in ("l15rev", "l15mom"):
        r = (snap45 / snap30).reindex(index=close.index, columns=close.columns) - 1
        return -r if signal == "l15rev" else r
    raise ValueError(signal)


def id5_matrix(open_, close, snap45) -> pd.DataFrame:
    last = snap45.reindex(index=close.index, columns=close.columns)
    past = np.log(close / open_).shift(1).rolling(4).sum()
    return -(past + np.log(last / open_))


def decision_dates(index: pd.DatetimeIndex, hold: int) -> list:
    return list(index[index.searchsorted(pd.Timestamp(FIRST_DECISION))::hold])


def _top(series: pd.Series, n: int) -> list[str]:
    return [t for t, _ in sorted(series.items(), key=lambda kv: (-kv[1], kv[0]))[:n]]


def select(rule: dict, row: pd.Series, held: list[str]) -> list[str]:
    """Band selection exactly as in short_horizon_v3: keep held names ranked within the band, fill from the top."""
    n = max(1, int(round(rule["fraction"] * len(row)))) if len(row) else 0
    if not n:
        return []
    order = _top(row, len(row))
    cutoff = set(order[:max(n, int(round(rule["band"] * len(row))))])
    keep = [t for t in held if t in cutoff]
    fill = [t for t in order if t not in keep][:max(0, n - len(keep))]
    return sorted(keep + fill)


def top_up_weights(picks: list[str], held_w: pd.Series, growth: pd.Series) -> pd.Series:
    """No-top-up weights: kept names keep their drifted weight, the rest of the book is split equally among the
    names bought; with nothing bought, the kept weights are scaled to sum to 1."""
    drift = held_w * growth.reindex(held_w.index).fillna(1.0)
    drift = drift / drift.sum() if drift.sum() > 0 else drift
    kept = [t for t in picks if t in drift.index]
    bought = [t for t in picks if t not in drift.index]
    w = pd.Series(0.0, picks)
    if kept:
        w[kept] = drift[kept]
    if bought:
        w[bought] = max(0.0, 1.0 - w.sum()) / len(bought)
    elif w.sum() > 0:
        w = w / w.sum()
    return w


def generate_targets(rule: dict, close: pd.DataFrame, scores: pd.DataFrame, decisions, members_on_fn,
                     scores2: pd.DataFrame | None = None, groups: pd.Series | None = None,
                     exclude: pd.DataFrame | None = None):
    index = close.index
    close_ff = close.ffill()
    strategy = pd.DataFrame(np.nan, index, close.columns)
    decisions = [d for d in pd.DatetimeIndex(decisions) if d in index and d >= pd.Timestamp(FIRST_DECISION)]
    detail, held, held_w, last_date = [], [], pd.Series(dtype=float), None
    for date, candidates in zip(decisions, members_on_fn(decisions)):
        priced = [t for t in sorted(candidates) if t in close.columns and pd.notna(close.at[date, t])]
        row = scores.loc[date, priced].dropna() if priced else pd.Series(dtype=float)
        if exclude is not None:
            row = row[~exclude.loc[date, row.index].to_numpy()]
        if rule["signal"] == "blend":
            other = scores2.loc[date, row.index].dropna()
            both = row.index.intersection(other.index)
            row = zscore(row[both]) + zscore(other[both])
        elif rule["signal"] == "rev5n" and len(row):
            row = neutralize(row, groups)
        ranked = list(row.index)
        picks = select(rule, row, held)
        strategy.loc[date] = 0.0
        if picks:
            if rule.get("no_top_up") and len(held_w):
                growth = close_ff.loc[date, held_w.index] / close_ff.loc[last_date, held_w.index]
                w = top_up_weights(picks, held_w, growth)
            else:
                w = pd.Series(1.0 / len(picks), picks)
            strategy.loc[date, picks] = w.reindex(picks).to_numpy()
            held_w = w
        else:
            held_w = pd.Series(dtype=float)
        held, last_date = picks, date
        detail.append({"date": date, "priced": priced, "ranked": ranked, "picks": picks})
    return strategy, detail
