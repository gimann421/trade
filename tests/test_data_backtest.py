import json
from datetime import datetime, timezone
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from core.backtest import load_strategy, run_backtest, save_result
from core.config import ROOT
from core.data import download_daily_bars, load_bars


def synthetic_bars(n=600, seed=0):
    rng = np.random.default_rng(seed)
    close = 100 * np.cumprod(1 + rng.normal(0.0004, 0.01, n))
    idx = pd.bdate_range("2020-01-01", periods=n)
    return pd.DataFrame({"open": close, "high": close, "low": close, "close": close,
                         "volume": 1_000_000}, index=idx)


def test_download_writes_csv_and_load_reads_it(tmp_path):
    bars = synthetic_bars(5)
    idx = pd.MultiIndex.from_arrays(
        [["SPY"] * 5, bars.index.tz_localize("America/New_York").tz_convert("UTC")],
        names=["symbol", "timestamp"])
    api_df = bars.set_axis(idx).assign(trade_count=1, vwap=1.0)
    client = SimpleNamespace(get_stock_bars=lambda req: SimpleNamespace(df=api_df))

    download_daily_bars("spy", datetime(2020, 1, 1, tzinfo=timezone.utc),
                        client=client, data_dir=tmp_path)
    loaded = load_bars("SPY", tmp_path)
    assert list(loaded.columns) == ["open", "high", "low", "close", "volume"]
    assert loaded.index[0] == pd.Timestamp("2020-01-01")
    assert np.allclose(loaded["close"].values, bars["close"].values)


def test_load_missing_bars_explains(tmp_path):
    with pytest.raises(FileNotFoundError, match="python -m core.data"):
        load_bars("NOPE", tmp_path)


def test_always_long_matches_buy_and_hold_minus_one_entry_cost():
    bars = synthetic_bars()
    result = run_backtest(bars, lambda b: pd.Series(1.0, index=b.index), cost_bps=10)
    hold = result["buy_and_hold"]["total_return"]
    strat = result["strategy"]["total_return"]
    first_day = bars["close"].pct_change().iloc[1]
    expected = (1 + hold) / (1 + first_day) * (1 + first_day - 0.001) - 1
    assert strat == pytest.approx(expected)
    assert result["strategy"]["trades"] == 1


def test_same_day_return_not_tradeable():
    # Trading on the return of the day the signal is computed would be perfect without the shift.
    bars = synthetic_bars()
    result = run_backtest(bars, lambda b: np.sign(b["close"].pct_change()).fillna(0), cost_bps=0)
    assert result["strategy"]["sharpe"] < 3


def test_future_peeking_strategy_rejected():
    bars = synthetic_bars()
    def cheat(b):
        return np.sign(b["close"].pct_change().shift(-1)).fillna(0)
    with pytest.raises(ValueError, match="future data"):
        run_backtest(bars, cheat)


def test_load_strategy_checks_name_and_version(tmp_path):
    strategy = load_strategy(ROOT / "strategies" / "sma_crossover_v1.py")
    assert strategy.STRATEGY_NAME == "sma_crossover" and strategy.VERSION == 1

    bad_name = tmp_path / "Crossover.py"
    bad_name.write_text("VERSION = 1\ndef generate_signals(b): pass\n")
    with pytest.raises(ValueError, match="_v<N>"):
        load_strategy(bad_name)

    mismatch = tmp_path / "thing_v2.py"
    mismatch.write_text("VERSION = 1\ndef generate_signals(b): pass\n")
    with pytest.raises(ValueError, match="VERSION must be 2"):
        load_strategy(mismatch)


def test_example_strategy_runs_and_saves(tmp_path):
    strategy = load_strategy(ROOT / "strategies" / "sma_crossover_v1.py")
    result = run_backtest(synthetic_bars(), strategy.generate_signals)
    path = save_result(result, strategy, "spy", backtests_dir=tmp_path)
    summary = json.loads(path.read_text())
    assert summary["strategy_file"] == "strategies/sma_crossover_v1.py"
    assert summary["params"] == {"fast": 50, "slow": 200}
    assert path.with_name(path.stem + "_equity.csv").exists()
