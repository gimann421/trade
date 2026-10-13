"""Hypotheses 34-70: one scan of 37 rotation and factor rules, each scored on its own.

Three families, all long-only, equal-weight, rebalanced at scheduled month-end closes, first
decision 2017-01-31 for every rule so all rules share the same windows:
  etf             hold the top k of a small ETF universe (9 sectors, or 6 regions) by one of four signals
  stock           hold the top decile / quintile of point-in-time S&P 500 members by one of seven signals
  stock + trend   the decile portfolio, but 100% BIL whenever VTI's close is not above its 200-day average

Signals are computed from data up to and including the decision close. Each signal returns a score
where higher is better, and NaN where the window lacks data (so a stock that has not traded for
long enough, or has gaps, is not ranked). See research/r6-factor-scan-2026-10-13.md.
Not a recommendation.
"""

import numpy as np
import pandas as pd

from core.universe import members_on

VERSION = 1
FIRST_DECISION = "2017-01-31"
TREND_DAYS = 200
CASH = "BIL"
SECTORS = ("XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY")
REGIONS = ("SPY", "QQQ", "IWM", "EFA", "EEM", "VNQ")
# name -> (lookback, skip, sign): total return over trading days t-lookback..t-skip, times sign
RETURN_SIGNALS = {"mom3": (63, 0, 1), "mom6": (126, 0, 1), "mom12_1": (252, 21, 1),
                  "mom6_1": (126, 21, 1), "rev1": (20, 0, -1)}
ETF_SIGNALS = ("mom3", "mom6", "mom12_1", "rev1")
STOCK_SIGNALS = ("mom12_1", "mom6_1", "resmom6_1", "rev1", "lowvol", "lowbeta", "high52")
RESMOM6_1 = {"start_lag": 126, "end_lag": 21, "min_valid": 105}  # same data rule as H33: all but one day


def build_rules() -> list[dict]:
    rules = []
    for universe, tickers, sizes in (("sect", SECTORS, (2, 3)), ("region", REGIONS, (1, 2))):
        for signal in ETF_SIGNALS:
            for k in sizes:
                rules.append({"id": f"etf_{universe}_{signal}_k{k}", "family": "etf", "tickers": list(tickers),
                              "signal": signal, "k": k})
    for signal in STOCK_SIGNALS:
        for size, fraction in (("decile", 0.1), ("quintile", 0.2)):
            rules.append({"id": f"stock_{signal}_{size}", "family": "stock", "signal": signal,
                          "fraction": fraction, "trend": False})
    for signal in STOCK_SIGNALS:
        rules.append({"id": f"stock_{signal}_decile_trend", "family": "stock", "signal": signal,
                      "fraction": 0.1, "trend": True})
    return rules


RULES = build_rules()


# --- signals ----------------------------------------------------------------------------------

def return_score(close: pd.DataFrame, lookback: int, skip: int, sign: int = 1) -> pd.DataFrame:
    """Total return over days t-lookback..t-skip; NaN if more than one return in the window is missing."""
    r = close.pct_change(fill_method=None)
    n = lookback - skip + 1
    total = np.log1p(r.clip(lower=-0.9999)).fillna(0.0).rolling(n).sum()
    valid = r.notna().rolling(n).sum() >= n - 1
    return sign * np.expm1(total).where(valid).shift(skip)


def rolling_beta(close: pd.DataFrame, market: pd.Series, window: int = 252, min_valid: int = 231) -> pd.DataFrame:
    r = close.pct_change(fill_method=None)
    m = market.pct_change(fill_method=None).reindex(r.index)
    ok = r.notna().mul(m.notna(), axis=0).astype(float)
    r0, m0 = r.fillna(0.0), m.fillna(0.0)
    roll = lambda x: x.rolling(window).sum()
    n = roll(ok)
    sr, sm = roll(r0 * ok), roll(ok.mul(m0, axis=0))
    srm, smm = roll((r0 * ok).mul(m0, axis=0)), roll(ok.mul(m0 ** 2, axis=0))
    cov = srm / n - (sr / n) * (sm / n)
    var = smm / n - (sm / n) ** 2
    return (cov / var).where((n >= min_valid) & (var > 0))


def score_matrix(name: str, close: pd.DataFrame, market: pd.Series | None = None) -> pd.DataFrame:
    """Score per date and ticker (higher is better) for every signal except resmom6_1."""
    if name in RETURN_SIGNALS:
        return return_score(close, *RETURN_SIGNALS[name])
    r = close.pct_change(fill_method=None)
    if name == "lowvol":
        return -r.rolling(252, min_periods=231).std()
    if name == "lowbeta":
        return -rolling_beta(close, market)
    if name == "high52":
        return close / close.rolling(252, min_periods=231).max()
    raise ValueError(f"unknown signal {name}")


def trend_series(market: pd.Series, days: int = TREND_DAYS) -> pd.Series:
    """True where the market's close is above its trailing average (needs a full window)."""
    avg = market.rolling(days, min_periods=days).mean()
    return (market > avg).where(avg.notna(), False)


# --- selection --------------------------------------------------------------------------------

def pick(scores: pd.Series, k: int | None = None, fraction: float | None = None) -> list[str]:
    """Top names by score; ties broken by ticker so the pick is deterministic."""
    s = scores.dropna()
    if s.empty:
        return []
    n = k if k is not None else max(1, int(round(fraction * len(s))))
    return [t for t, _ in sorted(s.items(), key=lambda kv: (-kv[1], kv[0]))[:n]]


def generate_targets(rule: dict, close: pd.DataFrame, scores: pd.DataFrame, decisions, membership=None,
                     trend: pd.Series | None = None):
    """Strategy and benchmark targets (NaN rows = no trade) and per-rebalance detail.

    close: raw closes (NaN where a name has no bar) including a CASH column; scores: score per
    date and ticker. The benchmark is equal weight of every priced candidate; a trend rule that is
    'off' holds 100% CASH while the benchmark stays invested.
    """
    index = close.index
    strategy = pd.DataFrame(np.nan, index, close.columns)
    benchmark = pd.DataFrame(np.nan, index, close.columns)
    decisions = [d for d in pd.DatetimeIndex(decisions) if d in index and d >= pd.Timestamp(FIRST_DECISION)]
    if rule["family"] == "etf":
        candidate_sets = [frozenset(rule["tickers"])] * len(decisions)
    else:
        candidate_sets = members_on(membership, decisions) if decisions else []
    detail = []
    for date, candidates in zip(decisions, candidate_sets):
        priced = [t for t in sorted(candidates) if t in close.columns and pd.notna(close.at[date, t])]
        row = scores.loc[date, priced] if priced else pd.Series(dtype=float)
        ranked = list(row.dropna().index)
        off = bool(rule.get("trend")) and not bool(trend.loc[date])
        picks = [CASH] if off else pick(row, rule.get("k"), rule.get("fraction"))
        strategy.loc[date] = 0.0
        benchmark.loc[date] = 0.0
        if picks:
            strategy.loc[date, picks] = 1.0 / len(picks)
        if priced:
            benchmark.loc[date, priced] = 1.0 / len(priced)
        detail.append({"date": date, "members": len(candidates), "priced": priced, "ranked": ranked,
                       "picks": picks, "off": off})
    return strategy, benchmark, detail
