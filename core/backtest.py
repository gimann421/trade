"""Daily backtester for strategies/<name>_v<N>.py.

A strategy module defines VERSION (matching its filename) and
generate_signals(bars) -> Series of target weights in [-1, 1], one per day,
using only data up to and including that day.

Fill assumption: a signal computed from day t's close is held over day t+1's
return, i.e. filled at day t's close. That is slightly optimistic; cost_bps
(charged per unit of turnover) is there to pay for it.

    python -m core.backtest strategies/sma_crossover_v1.py SPY
    python -m core.backtest strategies/sma_crossover_v1.py SPY --hypothesis-id 1 --verdict supports
    python -m core.backtest strategies/sma_crossover_v1.py SPY --start 2023-01-01   # score one window
"""

import argparse
import importlib.util
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from core.config import ROOT

BACKTESTS_DIR = ROOT / "backtests"
TRADING_DAYS = 252
STRATEGY_FILE = re.compile(r"^(?P<name>[a-z0-9_]+)_v(?P<version>\d+)\.py$")


def load_strategy(path: Path):
    path = Path(path)
    match = STRATEGY_FILE.match(path.name)
    if not match:
        raise ValueError(f"{path.name}: strategy files must be named <name>_v<N>.py")
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not callable(getattr(module, "generate_signals", None)):
        raise ValueError(f"{path.name} has no generate_signals(bars)")
    if getattr(module, "VERSION", None) != int(match["version"]):
        raise ValueError(f"{path.name}: VERSION must be {int(match['version'])}")
    module.STRATEGY_NAME = match["name"]
    return module


def _metrics(returns: pd.Series) -> dict:
    equity = (1 + returns).cumprod()
    years = len(returns) / TRADING_DAYS
    vol = returns.std() * np.sqrt(TRADING_DAYS)
    return {
        "total_return": float(equity.iloc[-1] - 1),
        "cagr": float(equity.iloc[-1] ** (1 / years) - 1) if years > 0 else 0.0,
        "ann_vol": float(vol),
        "sharpe": float(returns.mean() * TRADING_DAYS / vol) if vol > 0 else 0.0,
        "max_drawdown": float((equity / equity.cummax() - 1).min()),
    }


def _signals(bars: pd.DataFrame, generate_signals) -> pd.Series:
    return generate_signals(bars).reindex(bars.index).fillna(0.0).clip(-1, 1)


def check_no_lookahead(bars: pd.DataFrame, generate_signals, samples: int = 5) -> None:
    """Raise if a strategy's signals use future rows.

    Signals computed on data truncated at a cutoff must match the full-history
    signals up to that cutoff; any difference means the strategy peeked ahead.
    """
    full = _signals(bars, generate_signals)
    for cutoff in np.linspace(len(bars) // 2, len(bars) - 2, samples, dtype=int):
        partial = _signals(bars.iloc[:cutoff + 1], generate_signals)
        if not np.allclose(partial.values, full.iloc[:cutoff + 1].values):
            first = partial.index[~np.isclose(partial.values, full.iloc[:cutoff + 1].values)][0]
            raise ValueError(f"strategy uses future data: signal on {first.date()} changes "
                             f"when later bars are added")


def run_backtest(bars: pd.DataFrame, generate_signals, cost_bps: float = 5.0,
                 start: str | None = None, end: str | None = None) -> dict:
    """Backtest on the full history; report metrics only for [start, end] if given.

    Signals and positions are always computed on the full history, so a window starts
    with warmed-up indicators and the position carried in from the day before.
    """
    check_no_lookahead(bars, generate_signals)
    close = bars["close"]
    asset_returns = close.pct_change().fillna(0.0)
    target = _signals(bars, generate_signals)
    position = target.shift(1).fillna(0.0)
    turnover = position.diff().abs().fillna(position.abs())
    returns = position * asset_returns - turnover * cost_bps / 10_000

    window = slice(start, end)
    returns, asset_returns = returns.loc[window], asset_returns.loc[window]
    position, turnover = position.loc[window], turnover.loc[window]
    if returns.empty:
        raise ValueError(f"no bars between {start} and {end}")
    in_market = position > 0
    was_in = in_market.shift(1, fill_value=False)
    exposure_days = int(in_market.sum())

    return {
        "start": str(returns.index[0].date()),
        "end": str(returns.index[-1].date()),
        "days": len(returns),
        "cost_bps": cost_bps,
        "strategy": _metrics(returns) | {
            "exposure": float(position.abs().mean()),
            "trades": int((turnover > 0).sum()),
            "entries": int((in_market & ~was_in).sum()),
            "exits": int((~in_market & was_in).sum()),
            "exposure_days": exposure_days,
            "return_per_exposure_day": float(returns.sum() / exposure_days) if exposure_days else 0.0,
        },
        "buy_and_hold": _metrics(asset_returns) | {
            "mean_daily_return": float(asset_returns.mean()),
        },
        "equity_curve": (1 + returns).cumprod(),
    }


def _git_commit() -> str:
    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                                capture_output=True, text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                               capture_output=True, text=True, check=True).stdout.strip()
        return commit + ("-dirty" if dirty else "")
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def save_result(result: dict, strategy, symbol: str, backtests_dir: Path = BACKTESTS_DIR,
                window: str | None = None) -> Path:
    run_dir = backtests_dir / f"{strategy.STRATEGY_NAME}_v{strategy.VERSION}"
    run_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    stem = f"{symbol.upper()}_{window + '_' if window else ''}{stamp}"
    summary = {k: v for k, v in result.items() if k != "equity_curve"} | {
        "strategy_file": f"strategies/{strategy.STRATEGY_NAME}_v{strategy.VERSION}.py",
        "params": getattr(strategy, "PARAMS", {}),
        "symbol": symbol.upper(),
        "git_commit": _git_commit(),
        "run_at": stamp,
    }
    (run_dir / f"{stem}.json").write_text(json.dumps(summary, indent=2) + "\n")
    result["equity_curve"].rename("equity").to_csv(run_dir / f"{stem}_equity.csv", index_label="date")
    return run_dir / f"{stem}.json"


def main() -> None:
    from core.data import load_bars
    from core.ledger import VERDICTS, add_evidence, connect

    parser = argparse.ArgumentParser(description="Backtest a strategy file on cached daily bars")
    parser.add_argument("strategy", type=Path)
    parser.add_argument("symbol")
    parser.add_argument("--cost-bps", type=float, default=5.0)
    parser.add_argument("--start", help="first date to score (YYYY-MM-DD); signals still use all history")
    parser.add_argument("--end", help="last date to score (YYYY-MM-DD)")
    parser.add_argument("--hypothesis-id", type=int, help="log this run as evidence in the ledger")
    parser.add_argument("--verdict", choices=VERDICTS)
    args = parser.parse_args()
    if (args.hypothesis_id is None) != (args.verdict is None):
        parser.error("--hypothesis-id and --verdict go together")

    strategy = load_strategy(args.strategy)
    result = run_backtest(load_bars(args.symbol), strategy.generate_signals, args.cost_bps,
                          args.start, args.end)
    window = f"{result['start']}_{result['end']}" if args.start or args.end else None
    path = save_result(result, strategy, args.symbol, window=window)
    s, b = result["strategy"], result["buy_and_hold"]
    print(f"{args.symbol.upper()} {result['start']}..{result['end']}  "
          f"strategy: CAGR {s['cagr']:.1%} Sharpe {s['sharpe']:.2f} MaxDD {s['max_drawdown']:.1%}  |  "
          f"buy&hold: CAGR {b['cagr']:.1%} Sharpe {b['sharpe']:.2f} MaxDD {b['max_drawdown']:.1%}")
    print(f"saved {path.relative_to(ROOT)}")

    if args.hypothesis_id is not None:
        conn = connect()
        summary = (f"{strategy.STRATEGY_NAME}_v{strategy.VERSION} on {args.symbol.upper()} "
                   f"{result['start']}..{result['end']}: "
                   f"Sharpe {s['sharpe']:.2f} vs buy&hold {b['sharpe']:.2f}, MaxDD {s['max_drawdown']:.1%}")
        add_evidence(conn, args.hypothesis_id, "backtest", summary, args.verdict,
                     ref=str(path.relative_to(ROOT)))
        conn.close()
        print(f"logged evidence for hypothesis {args.hypothesis_id}")


if __name__ == "__main__":
    main()
