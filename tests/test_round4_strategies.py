import numpy as np
import pandas as pd
import pytest

from core.backtest import ROOT, load_strategy, run_backtest
from core.market_calendar import sessions_to_month_end, trading_days
from core.portfolio import load_portfolio_strategy, run_portfolio_backtest


def bars_on(index, close):
    close = np.asarray(close, float)
    return pd.DataFrame({"open": close, "high": close, "low": close, "close": close, "volume": 1e6}, index=index)


def test_sessions_to_month_end_counts_scheduled_sessions():
    idx = trading_days("2024-03-18", "2024-04-05")
    remaining = sessions_to_month_end(idx)
    # Good Friday (2024-03-29) is a holiday, so Thursday the 28th is the last session of March
    assert remaining[pd.Timestamp("2024-03-28")] == 0 and remaining[pd.Timestamp("2024-03-27")] == 1
    assert remaining[pd.Timestamp("2024-03-25")] == 3 and remaining[pd.Timestamp("2024-04-01")] > 10


def test_treasury_month_end_holds_the_last_three_sessions():
    idx = trading_days("2025-01-02", "2025-12-31")
    w = load_strategy(ROOT / "strategies" / "treasury_month_end_v1.py").generate_signals(bars_on(idx, np.full(len(idx), 100.0)))
    at = lambda d: w[pd.Timestamp(d)]
    # September 2025 ends Tue 30th: weight on the closes of the 25th, 26th, 29th earns the 26th, 29th, 30th
    assert [at(d) for d in ("2025-09-24", "2025-09-25", "2025-09-26", "2025-09-29", "2025-09-30", "2025-10-01")] == \
        [0, 1, 1, 1, 0, 0]
    assert w.sum() == 36                                      # 3 sessions x 12 months


def test_treasury_month_end_has_no_lookahead():
    idx = trading_days("2018-01-02", "2021-12-31")
    rng = np.random.default_rng(0)
    bars = bars_on(idx, 100 * np.cumprod(1 + rng.normal(0, 0.01, len(idx))))
    result = run_backtest(bars, load_strategy(ROOT / "strategies" / "treasury_month_end_v1.py").generate_signals)
    assert result["strategy"]["entries"] == 48 and result["strategy"]["exposure"] == pytest.approx(144 / len(idx), abs=0.01)


def tilt_bars(equity_path, bond_path, idx):
    return {"VTI": bars_on(idx, equity_path), "IEI": bars_on(idx, bond_path)}


def test_pension_tilt_fades_the_month_to_date_winner():
    module = load_portfolio_strategy(ROOT / "strategies" / "pension_tilt_v1.py")
    idx = trading_days("2024-01-02", "2024-03-28")
    feb = (idx >= "2024-02-01") & (idx <= "2024-02-29")
    equity = np.full(len(idx), 100.0)
    equity[feb] = 100 * np.cumprod(np.full(feb.sum(), 1.002))     # equities rally through February
    equity[idx > "2024-02-29"] = equity[feb][-1]
    w = module.generate_weights(tilt_bars(equity, np.full(len(idx), 50.0), idx), equity="VTI", bond="IEI")
    assert w.iloc[0].tolist() == [0.6, 0.4]
    jan = w.loc["2024-01-02":"2024-01-31"].dropna()
    assert list(jan.index) == [pd.Timestamp("2024-01-02"), pd.Timestamp("2024-01-31")]   # no tilt before an anchor exists
    late_feb = w.loc["2024-02-22":"2024-02-28"].dropna()                                 # T-5..T-1 of February
    assert len(late_feb) == 5 and np.allclose(late_feb["VTI"], 0.4)                    # underweight the winner
    assert w.loc["2024-02-29"].tolist() == [0.6, 0.4]                                    # back to 60/40 at T
    assert w.loc["2024-02-01":"2024-02-21"].isna().all().all()                           # no trading mid-month


def test_pension_tilt_reverts_when_the_drift_falls_below_threshold_and_skips_small_months():
    module = load_portfolio_strategy(ROOT / "strategies" / "pension_tilt_v1.py")
    idx = trading_days("2024-01-02", "2024-03-28")
    equity = np.full(len(idx), 100.0)
    feb_days = idx[(idx >= "2024-02-01") & (idx <= "2024-02-29")]
    for i, d in enumerate(feb_days):
        # -2% gives |C| = 0.49 pp (above 0.33); back to 100 closes the gap
        equity[idx.get_loc(d)] = 98.0 if d < pd.Timestamp("2024-02-23") else 100.0
    equity[idx > "2024-02-29"] = 100.05                                                 # tiny March drift: no tilt
    w = module.generate_weights(tilt_bars(equity, np.full(len(idx), 50.0), idx), equity="VTI", bond="IEI")
    assert w.loc["2024-02-22", "VTI"] == pytest.approx(0.8)      # equities lagged: overweight them (T-5)
    assert w.loc["2024-02-23", "VTI"] == pytest.approx(0.6)      # drift gone: back to 60/40
    assert w.loc["2024-02-26":"2024-02-28"].isna().all().all()   # nothing further to do
    assert w.loc["2024-03-20":"2024-03-27"].isna().all().all()   # March drift under 0.33 pp: no tilt


def test_pension_tilt_runs_without_lookahead():
    module = load_portfolio_strategy(ROOT / "strategies" / "pension_tilt_v1.py")
    idx = trading_days("2018-01-02", "2021-12-31")
    rng = np.random.default_rng(3)
    bars = tilt_bars(100 * np.cumprod(1 + rng.normal(0.0004, 0.01, len(idx))),
                     50 * np.cumprod(1 + rng.normal(0.0001, 0.003, len(idx))), idx)
    result = run_portfolio_backtest(bars, lambda b: module.generate_weights(b, equity="VTI", bond="IEI"))
    assert result["strategy"]["trades"] > 12 and result["strategy"]["exposure"] == pytest.approx(1.0, abs=0.01)
