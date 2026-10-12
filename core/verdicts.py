"""Shared scoring helpers for research rounds: kill rules, cross-symbol pass rule, placebo test.

A round's script maps each hypothesis to a strategy file, a per-cell kill rule and its
symbols, then uses these helpers. Thresholds come from the memos and are fixed before testing.
"""

import numpy as np
import pandas as pd

from core.backtest import TRADING_DAYS, _signals

PLACEBO_METRICS = ("sharpe", "return_per_exposure_day")


def drawdown_rule(r: dict, dd_margin: float = 0.05, sharpe_mult: float = 1.0) -> list[str]:
    """Fail reasons if Sharpe < sharpe_mult x buy-and-hold or max drawdown is not dd_margin shallower."""
    s, b = r["strategy"], r["buy_and_hold"]
    fails = []
    if s["sharpe"] < sharpe_mult * b["sharpe"]:
        fails.append(f"Sharpe {s['sharpe']:.2f} < {sharpe_mult:g}x buy&hold {b['sharpe']:.2f}")
    if s["max_drawdown"] - b["max_drawdown"] < dd_margin - 1e-9:  # exactly the margin passes
        fails.append(f"MaxDD {s['max_drawdown']:.1%} not {dd_margin * 100:g}pts better than "
                     f"{b['max_drawdown']:.1%}")
    return fails


def per_day_rule(mult: float, sharpe_mult: float = 1.0):
    """Fail reasons if Sharpe < sharpe_mult x buy-and-hold or return per exposure day < mult x B&H daily mean."""
    def rule(r: dict) -> list[str]:
        s, b = r["strategy"], r["buy_and_hold"]
        fails = []
        if s["sharpe"] < sharpe_mult * b["sharpe"]:
            fails.append(f"Sharpe {s['sharpe']:.2f} < {sharpe_mult:g}x buy&hold {b['sharpe']:.2f}")
        if s["return_per_exposure_day"] < mult * b["mean_daily_return"]:
            fails.append(f"return/exposure day {s['return_per_exposure_day']:.3%} < "
                         f"{mult:g}x buy&hold {b['mean_daily_return']:.3%}")
        return fails
    return rule


def symbol_status(cells: dict[str, dict[str, str]], min_symbols: int) -> str:
    """Combine per-cell verdicts into a hypothesis status.

    cells maps symbol -> {window: "supports" | "contradicts" | "inconclusive"}. A symbol passes
    if every window supports. Supported needs >= min_symbols passing symbols; rejected when even
    counting every undecided symbol as a pass could not reach min_symbols; otherwise testing.
    """
    passing = sum(all(v == "supports" for v in w.values()) for w in cells.values())
    possible = sum(all(v != "contradicts" for v in w.values()) for w in cells.values())
    if passing >= min_symbols:
        return "supported"
    return "rejected" if possible < min_symbols else "testing"


def _metric(asset: np.ndarray, position: np.ndarray, cost_bps: float, metric: str) -> float:
    turnover = np.abs(np.diff(position, prepend=0.0))
    returns = position * asset - turnover * cost_bps / 10_000
    if metric == "sharpe":
        vol = returns.std(ddof=1)
        return float(returns.mean() * TRADING_DAYS / vol) if vol > 0 else 0.0
    days = (position > 0).sum()
    return float(returns.sum() / days) if days else 0.0


def placebo_percentile(asset: np.ndarray, position: np.ndarray, cost_bps: float = 5.0,
                       metric: str = "sharpe", n: int = 1000, seed: int = 0,
                       min_shift: int = TRADING_DAYS) -> float:
    """Share of placebo runs the real position beats (1.0 = beats all).

    A placebo is the same position series circularly shifted by a random number of days
    (at least min_shift away from alignment), so it keeps the real strategy's exposure,
    holding periods and trade count but not its timing against the asset.
    """
    if metric not in PLACEBO_METRICS:
        raise ValueError(f"metric must be one of {PLACEBO_METRICS}")
    asset, position = np.asarray(asset, float), np.asarray(position, float)
    if len(asset) != len(position) or len(asset) <= 2 * min_shift:
        raise ValueError("need equal-length series longer than twice min_shift")
    actual = _metric(asset, position, cost_bps, metric)
    shifts = np.random.default_rng(seed).integers(min_shift, len(asset) - min_shift + 1, size=n)
    placebo = np.array([_metric(asset, np.roll(position, k), cost_bps, metric) for k in shifts])
    return float((placebo < actual).mean())


def window_arrays(bars: pd.DataFrame, generate_signals, start=None, end=None):
    """(asset returns, position) over [start, end], positions from full-history signals."""
    asset = bars["close"].pct_change().fillna(0.0)
    position = _signals(bars, generate_signals).shift(1).fillna(0.0)
    window = slice(start, end)
    return asset.loc[window].to_numpy(), position.loc[window].to_numpy()
