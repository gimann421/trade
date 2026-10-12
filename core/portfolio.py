"""Daily multi-symbol backtester for strategies/<name>_v<N>.py that define generate_weights.

A portfolio strategy module defines VERSION (matching its filename) and
generate_weights(bars_by_symbol) -> DataFrame of target weights, one column per symbol:

  * Bars are aligned to the dates every symbol has before the strategy sees them.
  * A row is either all-NaN ("no trade today: let the portfolio drift") or finite weights in
    [0, 1] that sum to at most 1; the remainder is cash. A strategy may return only its
    rebalance dates; missing dates count as "no trade".
  * Weights computed from day t's close are traded at day t's close and held over day t+1's
    return, the same convention as core.backtest. Costs are cost_bps times the traded fraction
    of the portfolio, where trades are measured against the drifted holdings, so a strategy
    that only rebalances monthly pays for monthly trading, not daily.
  * Cash earns cash_return per year (default 0); hold a T-bill ETF such as BIL to earn the
    risk-free rate instead.

Each run is also scored against benchmarks on the same universe (equal weight held, equal
weight rebalanced monthly, inverse-volatility monthly, and 60/40 SPY/TLT when both are present).

    python -m core.portfolio strategies/<name>_v1.py SPY EFA TLT GLD --start 2023-01-01
"""

import argparse
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

from core.backtest import STRATEGY_FILE, TRADING_DAYS, _metrics, save_result
from core.config import ROOT
from core.market_calendar import next_trading_day

TOLERANCE = 1e-9


def load_portfolio_strategy(path: Path):
    path = Path(path)
    match = STRATEGY_FILE.match(path.name)
    if not match:
        raise ValueError(f"{path.name}: strategy files must be named <name>_v<N>.py")
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not callable(getattr(module, "generate_weights", None)):
        raise ValueError(f"{path.name} has no generate_weights(bars_by_symbol)")
    if getattr(module, "VERSION", None) != int(match["version"]):
        raise ValueError(f"{path.name}: VERSION must be {int(match['version'])}")
    module.STRATEGY_NAME = match["name"]
    return module


def align(bars_by_symbol: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Restrict every symbol to the dates all of them have."""
    index = None
    for bars in bars_by_symbol.values():
        index = bars.index if index is None else index.intersection(bars.index)
    if index is None or len(index) < 2:
        raise ValueError("symbols share fewer than two dates")
    return {symbol: bars.loc[index] for symbol, bars in bars_by_symbol.items()}


def month_ends(index: pd.DatetimeIndex) -> np.ndarray:
    """True on each bar whose next scheduled trading day falls in a later month.

    Decided from the exchange calendar (core.market_calendar), not from the next bar in the data,
    so the answer for a date never depends on bars after it: truncating the history does not
    invent a month-end, and the final bar counts only if it really is the last session of a month.
    """
    return np.asarray(next_trading_day(index).to_period("M") != index.to_period("M"))


def targets_from(bars_by_symbol, generate_weights, signal_only: tuple = ()) -> pd.DataFrame:
    """Strategy output reindexed to the aligned dates and validated.

    signal_only symbols are passed to the strategy (for example a canary used only to read
    risk appetite) but cannot be held: their columns must be zero or NaN and are dropped.
    """
    close_index = next(iter(bars_by_symbol.values())).index
    symbols = list(bars_by_symbol)
    tradable = [s for s in symbols if s not in signal_only]
    if not tradable:
        raise ValueError("every symbol is signal-only")
    raw = generate_weights(bars_by_symbol)
    if set(raw.columns) != set(symbols):
        raise ValueError(f"weights must have exactly the columns {symbols}, got {list(raw.columns)}")
    full = raw[symbols].astype(float).reindex(close_index)
    for symbol in signal_only:
        if (full[symbol].abs() > TOLERANCE).any():
            raise ValueError(f"{symbol} is signal-only and cannot carry weight")
    weights = full[tradable]
    partial = weights.isna().any(axis=1) & weights.notna().any(axis=1)
    if partial.any():
        raise ValueError(f"row {weights.index[partial][0].date()} mixes NaN and weights; "
                         f"use all-NaN for 'no trade'")
    values = weights.to_numpy()
    if np.nanmin(values, initial=0.0) < -TOLERANCE or np.nanmax(values, initial=0.0) > 1 + TOLERANCE:
        raise ValueError("weights must be in [0, 1]")
    if (weights.sum(axis=1, min_count=1) > 1 + TOLERANCE).any():
        raise ValueError("weights must sum to at most 1 (the rest is cash)")
    return weights.clip(0.0, 1.0)


def check_no_lookahead(bars_by_symbol, generate_weights, samples: int = 5,
                       signal_only: tuple = ()) -> None:
    """Raise if weights on or before a cutoff change when later bars are added."""
    full = targets_from(bars_by_symbol, generate_weights, signal_only)
    n = len(full)
    for cutoff in np.linspace(n // 2, n - 2, samples, dtype=int):
        partial_bars = {s: b.iloc[:cutoff + 1] for s, b in bars_by_symbol.items()}
        partial = targets_from(partial_bars, generate_weights, signal_only)
        a, b = partial.to_numpy(), full.iloc[:cutoff + 1].to_numpy()
        if not np.allclose(a, b, equal_nan=True):
            bad = ~np.isclose(a, b, equal_nan=True).all(axis=1)
            raise ValueError(f"strategy uses future data: weights on {partial.index[bad][0].date()} "
                             f"change when later bars are added")


def simulate(close: pd.DataFrame, targets: pd.DataFrame, cost_bps: float = 5.0,
             cash_return: float = 0.0) -> dict:
    """Run the targets through the portfolio; returns daily net returns and diagnostics."""
    returns = close.pct_change().fillna(0.0).to_numpy()
    target = targets.to_numpy()
    n, k = returns.shape
    cash_daily = (1 + cash_return) ** (1 / TRADING_DAYS) - 1
    weights, cash = np.zeros(k), 1.0
    net, traded, held = np.zeros(n), np.zeros(n), np.zeros(n)
    start_weights, start_cash = np.zeros((n, k)), np.zeros(n)
    for t in range(n):
        held[t] = weights.sum()
        start_weights[t], start_cash[t] = weights, cash
        gross = float(weights @ returns[t] + cash * cash_daily)
        growth = 1.0 + gross
        drifted = weights * (1 + returns[t]) / growth
        cash_drifted = cash * (1 + cash_daily) / growth
        cost = 0.0
        if not np.isnan(target[t, 0]):
            traded[t] = np.abs(target[t] - drifted).sum()
            cost = traded[t] * cost_bps / 10_000
            weights, cash = target[t].copy(), 1.0 - target[t].sum()
        else:
            weights, cash = drifted, cash_drifted
        net[t] = gross - cost
    index = close.index
    return {"returns": pd.Series(net, index), "traded": pd.Series(traded, index),
            "held": pd.Series(held, index),
            # holdings at the start of each day, before that day's return (used by the placebo)
            "weights": pd.DataFrame(start_weights, index, close.columns),
            "cash": pd.Series(start_cash, index)}


# --- benchmarks on the same universe -------------------------------------------------------

def _rebalance_rows(index, weights_at: np.ndarray, monthly: bool) -> pd.DataFrame:
    """Targets on the first bar and (if monthly) every month end; NaN elsewhere."""
    rows = np.full(weights_at.shape, np.nan)
    mask = month_ends(index) if monthly else np.zeros(len(index), bool)
    mask[0] = True
    rows[mask] = weights_at[mask]
    return rows


def equal_weight(bars, monthly: bool) -> pd.DataFrame:
    close = pd.DataFrame({s: b["close"] for s, b in bars.items()})
    flat = np.full(close.shape, 1.0 / close.shape[1])
    return pd.DataFrame(_rebalance_rows(close.index, flat, monthly), close.index, close.columns)


def inverse_vol(bars, window: int = 63, cash_symbols: tuple = ()) -> pd.DataFrame:
    """Inverse-volatility weights, monthly. Cash assets (for example BIL) get weight 0: their
    tiny volatility would otherwise make this benchmark almost entirely cash."""
    close = pd.DataFrame({s: b["close"] for s, b in bars.items()})
    vol = close.pct_change().rolling(window).std()
    inverse = 1.0 / vol
    for symbol in cash_symbols:
        if symbol in inverse and inverse.shape[1] > 1:
            inverse[symbol] = 0.0
    weights = (inverse.div(inverse.sum(axis=1), axis=0)).to_numpy()
    rows = _rebalance_rows(close.index, weights, monthly=True)
    # no weights until the volatility window has filled: stay in cash (NaN row = no trade)
    rows[np.isnan(weights).any(axis=1)] = np.nan
    return pd.DataFrame(rows, close.index, close.columns)


def sixty_forty(bars, equity: str = "SPY", bond: str = "TLT") -> pd.DataFrame:
    close = pd.DataFrame({s: b["close"] for s, b in bars.items()})
    flat = np.zeros(close.shape)
    flat[:, list(close.columns).index(equity)] = 0.6
    flat[:, list(close.columns).index(bond)] = 0.4
    return pd.DataFrame(_rebalance_rows(close.index, flat, monthly=True), close.index, close.columns)


def benchmark_targets(bars, cash_symbols: tuple = ()) -> dict[str, pd.DataFrame]:
    out = {"equal_weight_hold": equal_weight(bars, monthly=False),
           "equal_weight_monthly": equal_weight(bars, monthly=True),
           "inverse_vol_monthly": inverse_vol(bars, cash_symbols=cash_symbols)}
    if "SPY" in bars and "TLT" in bars:
        out["sixty_forty"] = sixty_forty(bars)
    return out


# --- backtest ------------------------------------------------------------------------------

def prepare(bars_by_symbol, generate_weights, cost_bps: float = 5.0, cash_return: float = 0.0,
            signal_only: tuple = ()):
    """Align, check for look-ahead, and simulate. Returns (bars, close, run) for tradable symbols."""
    bars = align(bars_by_symbol)
    check_no_lookahead(bars, generate_weights, signal_only=signal_only)
    tradable = {s: b for s, b in bars.items() if s not in signal_only}
    close = pd.DataFrame({s: b["close"] for s, b in tradable.items()})
    run = simulate(close, targets_from(bars, generate_weights, signal_only), cost_bps, cash_return)
    return tradable, close, run


def run_portfolio_backtest(bars_by_symbol, generate_weights, cost_bps: float = 5.0,
                           start: str | None = None, end: str | None = None,
                           cash_return: float = 0.0, signal_only: tuple = (),
                           cash_symbols: tuple = ()) -> dict:
    """Backtest on the full history; report metrics only for [start, end] if given.

    Weights and holdings are always simulated on the full history, so a window starts with
    warmed-up indicators and the portfolio carried in from the day before. signal_only symbols
    inform the strategy but are neither held nor part of the benchmarks; cash_symbols (for
    example BIL) are held and benchmarked, except in the inverse-volatility benchmark.
    """
    tradable, close, run = prepare(bars_by_symbol, generate_weights, cost_bps, cash_return, signal_only)
    window = slice(start, end)

    def summarise(run):
        returns, traded, held = (run[k].loc[window] for k in ("returns", "traded", "held"))
        if returns.empty:
            raise ValueError(f"no bars between {start} and {end}")
        years = len(returns) / TRADING_DAYS
        return returns, _metrics(returns) | {
            "exposure": float(held.mean()),
            "trades": int((traded > TOLERANCE).sum()),
            "annual_turnover": float(traded.sum() / years),
        }

    returns, metrics = summarise(run)
    benchmarks = {name: summarise(simulate(close, t, cost_bps, cash_return))[1]
                  for name, t in benchmark_targets(tradable, cash_symbols).items()}
    return {
        "start": str(returns.index[0].date()), "end": str(returns.index[-1].date()),
        "days": len(returns), "cost_bps": cost_bps, "cash_return": cash_return,
        "symbols": list(tradable), "signal_only": list(signal_only),
        "strategy": metrics,
        "benchmarks": benchmarks,
        "equity_curve": (1 + returns).cumprod(),
    }


def portfolio_placebo_percentile(close: pd.DataFrame, run: dict, start=None, end=None,
                                 cost_bps: float = 5.0, cash_return: float = 0.0, n: int = 1000,
                                 seed: int = 0, min_shift: int = TRADING_DAYS) -> float:
    """Share of placebo runs whose Sharpe the strategy's Sharpe beats (1.0 = beats all).

    A placebo is the strategy's own daily holdings (and the trading costs that go with them)
    circularly shifted by a random number of days, at least min_shift from alignment, against the
    assets' returns: same allocations, same turnover, wrong timing.
    """
    window = slice(start, end)
    ret = close.pct_change().fillna(0.0).loc[window].to_numpy()
    weights = run["weights"].loc[window].to_numpy()
    cash = run["cash"].loc[window].to_numpy()
    traded = run["traded"].loc[window].to_numpy()
    if len(ret) <= 2 * min_shift:
        raise ValueError("window too short for the placebo shift")
    cash_daily = (1 + cash_return) ** (1 / TRADING_DAYS) - 1
    cost = cost_bps / 10_000

    def sharpe(w, c, tr):
        net = (w * ret).sum(axis=1) + c * cash_daily - tr * cost
        vol = net.std(ddof=1)
        return float(net.mean() * TRADING_DAYS / vol) if vol > 0 else 0.0

    actual = sharpe(weights, cash, traded)
    shifts = np.random.default_rng(seed).integers(min_shift, len(ret) - min_shift + 1, size=n)
    placebo = np.array([sharpe(np.roll(weights, k, axis=0), np.roll(cash, k), np.roll(traded, k))
                        for k in shifts])
    return float((placebo < actual).mean())


def main() -> None:
    from core.data import load_bars

    parser = argparse.ArgumentParser(description="Backtest a portfolio strategy on cached daily bars")
    parser.add_argument("strategy", type=Path)
    parser.add_argument("symbols", nargs="+")
    parser.add_argument("--cost-bps", type=float, default=5.0)
    parser.add_argument("--cash-return", type=float, default=0.0, help="annual return on cash")
    parser.add_argument("--start", help="first date to score (YYYY-MM-DD); weights still use all history")
    parser.add_argument("--end", help="last date to score (YYYY-MM-DD)")
    args = parser.parse_args()

    strategy = load_portfolio_strategy(args.strategy)
    symbols = [s.upper() for s in args.symbols]
    result = run_portfolio_backtest({s: load_bars(s) for s in symbols}, strategy.generate_weights,
                                    args.cost_bps, args.start, args.end, args.cash_return,
                                    cash_symbols=("BIL",) if "BIL" in symbols else ())
    window = f"{result['start']}_{result['end']}" if args.start or args.end else None
    path = save_result(result, strategy, "-".join(symbols), window=window)
    print(f"{'-'.join(symbols)} {result['start']}..{result['end']}")
    for name, m in {"strategy": result["strategy"], **result["benchmarks"]}.items():
        print(f"  {name:22s} CAGR {m['cagr']:6.1%} Sharpe {m['sharpe']:5.2f} MaxDD {m['max_drawdown']:6.1%} "
              f"exposure {m['exposure']:4.0%} turnover/yr {m['annual_turnover']:5.1f}")
    print(f"saved {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
