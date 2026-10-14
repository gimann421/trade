"""Forward shadow record for single-symbol signal rules (strategies with generate_signals(bars)).

Same contract as core.paper_runner for stock rules: the record is rebuilt from the start date on
freshly downloaded bars with the code the backtest used (core.backtest return arithmetic: position is
the previous close's target, cost on turnover), and paper/<rule id>/ gets nav.csv, signals.csv and
status.json. signals.csv is write-once: a later run recomputes the targets and flags any difference
instead of overwriting. Only signals that fire at a close on or after `start` count: a hold that was
already running before the start date is dropped. Nothing here ever sends an order.
"""

import pandas as pd

from core.backtest import load_strategy
from core.config import ROOT

COST_BPS = 5.0
HISTORY_DAYS = 400


def forward_targets(bars: pd.DataFrame, generate_signals, start) -> pd.Series:
    """Targets from the full history, zero before `start` and zero for any hold already running then."""
    target = generate_signals(bars).reindex(bars.index).fillna(0.0).clip(-1, 1)
    start = pd.Timestamp(start)
    on = (target != 0).to_numpy()
    out = target.copy()
    i = 0
    while i < len(on):
        if not on[i]:
            i += 1
            continue
        j = i
        while j + 1 < len(on) and on[j + 1]:
            j += 1
        if target.index[i] < start:          # this hold began before the forward record did
            out.iloc[i:j + 1] = 0.0
        i = j + 1
    out[out.index < start] = 0.0
    return out


def run_signal_rule(cfg: dict, session, bars: pd.DataFrame, out_dir=None, strategy=None) -> dict:
    session, start = pd.Timestamp(session), pd.Timestamp(cfg["start"])
    status = {"rule": cfg["rule"], "kind": "signal", "symbol": cfg["symbol"], "strategy": cfg["strategy"],
              "asof": str(session.date()), "start": str(start.date())}
    if session < start or bars.index[-1] < start:
        status["state"] = "waiting"
        _write(out_dir, "status.json", status)
        return status
    if bars.index[-1] < session:
        from core.paper_runner import DataNotReady
        raise DataNotReady(f"latest bar is {bars.index[-1].date()}, but the last completed session is {session.date()}")
    strategy = strategy or load_strategy(ROOT / "strategies" / f"{cfg['strategy']}.py")
    bars = bars.loc[:session]
    target = forward_targets(bars, strategy.generate_signals, start)
    position = target.shift(1).fillna(0.0)
    turnover = position.diff().abs().fillna(position.abs())
    asset = bars["close"].pct_change().fillna(0.0)
    rets = (position * asset - turnover * COST_BPS / 10_000).loc[start:]
    initial = float(cfg.get("initial_cash", 100_000))
    nav = pd.DataFrame({"nav": initial * (1 + rets).cumprod(), "benchmark_nav": initial * (1 + asset.loc[start:]).cumprod(),
                        "position": position.loc[start:]})
    nav.index.name = "date"

    new = pd.DataFrame({"target": target.loc[start:], "close": bars["close"].loc[start:]})
    new.index.name = "date"
    changed = []
    stored = _read_signals(out_dir)
    if stored is not None:
        for date, row in stored.iterrows():
            if date in new.index and abs(row["target"] - new.at[date, "target"]) > 1e-9:
                changed.append({"date": str(date.date()), "stored": row["target"], "recomputed": float(new.at[date, "target"])})
        new = pd.concat([stored, new.loc[new.index > stored.index[-1]]]) if len(stored) else new
    entries = int(((target.loc[start:] > 0) & (target.loc[start:].shift(1, fill_value=0.0) == 0)).sum())
    status |= {"state": "running", "days": len(nav), "nav": float(nav["nav"].iloc[-1]),
               "benchmark_nav": float(nav["benchmark_nav"].iloc[-1]),
               "excess_return": float(nav["nav"].iloc[-1] / nav["benchmark_nav"].iloc[-1] - 1),
               "total_return": float(nav["nav"].iloc[-1] / initial - 1), "entries": entries,
               "in_position": bool(target.iloc[-1] > 0), "decisions_changed_since_recorded": changed}
    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        nav.to_csv(out_dir / "nav.csv")
        new.to_csv(out_dir / "signals.csv")
    _write(out_dir, "status.json", status)
    return status


def _read_signals(out_dir):
    if out_dir is None or not (out_dir / "signals.csv").exists():
        return None
    return pd.read_csv(out_dir / "signals.csv", index_col="date", parse_dates=True)


def _write(out_dir, name, obj):
    from core.paper_runner import _write_json
    _write_json(out_dir, name, obj)


def fetch_bars(symbol: str, start, end) -> pd.DataFrame:
    """Daily bars through the same download path as the backtests, in a throwaway directory."""
    import tempfile
    from datetime import timezone
    from pathlib import Path

    from core.data import download_daily_bars, load_bars
    with tempfile.TemporaryDirectory() as tmp:
        download_daily_bars(symbol, pd.Timestamp(start).to_pydatetime().replace(tzinfo=timezone.utc), data_dir=Path(tmp))
        return load_bars(symbol, Path(tmp))
