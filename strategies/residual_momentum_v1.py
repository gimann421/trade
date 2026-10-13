"""Hypothesis 33: residual momentum, top decile of point-in-time S&P 500 members.

At each month-end close t, every member with at least 231 valid daily returns among the 232
trading days t-252..t-21 is scored: its daily returns are regressed on a constant and three ETF
factors (MKT = VTI - BIL, SMB = IWM - IWB, HML = IWD - IWF) over the valid days; the residual
return keeps the constant (stock return minus betas x factors); score = its mean / its sd. The
top decile is held equal-weight from the close of t to the next month-end close. The benchmark
holds every member with a close on t, equal-weight, from the same first rebalance.
See research/r5-residual-momentum-2026-10-13.md. Not a recommendation.

Unlike the other portfolio strategies this one needs the membership history and stock closes
on an unaligned calendar (stocks list and delist), so generate_weights takes them directly.
"""

import numpy as np
import pandas as pd

from core.universe import members_on

VERSION = 1
PARAMS = {"start_lag": 252, "end_lag": 21, "min_valid": 231, "decile": 0.1}
FACTOR_ETFS = ("VTI", "BIL", "IWM", "IWB", "IWD", "IWF")


def factor_returns(etf_close: pd.DataFrame) -> pd.DataFrame:
    r = etf_close.pct_change(fill_method=None)
    return pd.DataFrame({"MKT": r["VTI"] - r["BIL"], "SMB": r["IWM"] - r["IWB"], "HML": r["IWD"] - r["IWF"]})


def _window(returns: pd.DataFrame, factors: pd.DataFrame, t_pos: int, start_lag: int, end_lag: int):
    lo, hi = max(t_pos - start_lag, 0), t_pos - end_lag
    if hi < lo:
        return None, None
    f = factors.iloc[lo:hi + 1]
    y = returns.iloc[lo:hi + 1].copy()
    y[f.isna().any(axis=1).to_numpy()] = np.nan  # a day with no factor data is invalid for all
    return y, f.fillna(0.0)


def residual_scores(returns, factors, t_pos, tickers, start_lag=252, end_lag=21, min_valid=231) -> pd.Series:
    """Score = mean / sd of (return - betas x factors) over the formation window, per ticker."""
    y, f = _window(returns[tickers], factors, t_pos, start_lag, end_lag)
    if y is None:
        return pd.Series(dtype=float)
    valid = y.notna()
    keep = valid.sum() >= min_valid
    y, valid = y.loc[:, keep], valid.loc[:, keep]
    x = np.column_stack([np.ones(len(f)), f.to_numpy()])
    scores = {}
    full = valid.all()
    if full.any():  # one least-squares solve for every ticker with no gaps
        yy = y.loc[:, full].to_numpy()
        beta = np.linalg.lstsq(x, yy, rcond=None)[0]
        resid = yy - x[:, 1:] @ beta[1:]
        sd = resid.std(axis=0, ddof=1)
        scores.update(zip(y.columns[full], np.where(sd > 0, resid.mean(axis=0) / np.where(sd > 0, sd, 1), np.nan)))
    for ticker in y.columns[~full]:
        m = valid[ticker].to_numpy()
        yy, xx = y[ticker].to_numpy()[m], x[m]
        beta = np.linalg.lstsq(xx, yy, rcond=None)[0]
        resid = yy - xx[:, 1:] @ beta[1:]
        sd = resid.std(ddof=1)
        scores[ticker] = resid.mean() / sd if sd > 0 else np.nan
    return pd.Series(scores, dtype=float).dropna()


def total_return_scores(returns, factors, t_pos, tickers, start_lag=252, end_lag=21, min_valid=231) -> pd.Series:
    """Plain 12-1 momentum on the same window and data rule (reported for comparison only)."""
    y, _ = _window(returns[tickers], factors, t_pos, start_lag, end_lag)
    if y is None:
        return pd.Series(dtype=float)
    y = y.loc[:, y.notna().sum() >= min_valid]
    return (1 + y.fillna(0.0)).prod() - 1


def top_decile(scores: pd.Series, decile: float) -> list:
    """Highest scores first; ties broken by ticker so the pick is deterministic."""
    if scores.empty:
        return []
    n = max(1, int(round(decile * len(scores))))
    order = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    return [t for t, _ in order[:n]]


def generate_weights(close: pd.DataFrame, factors: pd.DataFrame, membership: pd.Series,
                     decision_dates, score=residual_scores, start_lag=PARAMS["start_lag"],
                     end_lag=PARAMS["end_lag"], min_valid=PARAMS["min_valid"], decile=PARAMS["decile"]):
    """Strategy and benchmark targets (NaN rows = no trade) plus per-rebalance detail.

    close: raw stock closes on the trading-day index (NaN where a stock has no bar); factors on
    the same index. Nothing is held before the first decision date that ranks any stock.
    """
    returns = close.pct_change(fill_method=None)
    index = close.index
    strategy = pd.DataFrame(np.nan, index, close.columns)
    benchmark = pd.DataFrame(np.nan, index, close.columns)
    detail = []
    decision_dates = [d for d in pd.DatetimeIndex(decision_dates) if d in index]
    for date, members in zip(decision_dates, members_on(membership, decision_dates) if decision_dates else []):
        t_pos = index.get_loc(date)
        priced = [t for t in sorted(members) if t in close.columns and pd.notna(close.iat[t_pos, close.columns.get_loc(t)])]
        scores = score(returns, factors, t_pos, priced, start_lag, end_lag, min_valid)
        picks = top_decile(scores, decile)
        if not picks and not detail:
            continue  # warm-up: nothing ranked yet
        strategy.loc[date] = 0.0
        if picks:
            strategy.loc[date, picks] = 1.0 / len(picks)
        benchmark.loc[date] = 0.0
        benchmark.loc[date, priced] = 1.0 / len(priced)
        detail.append({"date": date, "members": len(members), "priced": priced,
                       "ranked": list(scores.index), "picks": picks})
    return strategy, benchmark, detail
