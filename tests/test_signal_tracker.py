import numpy as np
import pandas as pd
import pytest

from core import signal_tracker as st
from core.backtest import run_backtest
from core.market_calendar import trading_days
from research import three_era_screen as screen


def bars(n_days=300, seed=2):
    index = trading_days("2023-01-03", "2024-04-30")[:n_days]
    rng = np.random.default_rng(seed)
    close = 100 * np.cumprod(1 + rng.normal(0.0004, 0.01, len(index)))
    return pd.DataFrame({"open": close * (1 + rng.normal(0, 0.003, len(index))), "close": close}, index)


def every_tenth(b):
    s = pd.Series(0.0, b.index)
    for i in range(5, len(b), 10):
        s.iloc[i:i + 3] = 1.0           # 3-day holds, one flat bar between them at most
    return s


class Strategy:
    generate_signals = staticmethod(every_tenth)


CFG = {"rule": "t", "symbol": "XLK", "strategy": "gap_fade_washout_v1", "start": "2023-06-01", "initial_cash": 100_000}


def test_hold_running_at_the_start_date_is_dropped_and_earlier_days_are_flat():
    b = bars()
    raw = every_tenth(b)
    first_on = raw[raw > 0].index
    start = first_on[31]                  # a day inside a 3-day hold (holds start every 10 bars, 3 bars long)
    assert raw.loc[start] == 1 and raw.shift(1).loc[start] == 1
    got = st.forward_targets(b, every_tenth, start)
    assert (got.loc[:start] == 0).all()                      # nothing before the start, and the running hold is dropped
    later = raw.index[raw.index > start]
    next_hold = later[raw.loc[later] > 0]
    after_run = next_hold[next_hold > start + pd.Timedelta(days=5)]
    assert got.loc[after_run[0]] == 1                        # the next hold that begins after the start is kept
    assert got.loc[start + pd.Timedelta(days=1):].sum() > 0


def test_nav_matches_the_backtest_engine_over_the_forward_window(tmp_path):
    b = bars()
    session = b.index[-1]
    status = st.run_signal_rule(CFG, session, b, tmp_path, Strategy)
    assert status["state"] == "running"
    targets = st.forward_targets(b, every_tenth, CFG["start"])
    result = run_backtest(b, lambda x: targets, start=CFG["start"])
    nav = pd.read_csv(tmp_path / "nav.csv", index_col="date", parse_dates=True)["nav"]
    pd.testing.assert_series_equal(nav, 100_000 * result["equity_curve"], check_names=False, rtol=1e-9)


def test_signals_are_write_once_and_changes_are_flagged(tmp_path):
    b = bars()
    st.run_signal_rule(CFG, b.index[-1], b, tmp_path, Strategy)
    stored = pd.read_csv(tmp_path / "signals.csv", index_col="date", parse_dates=True)
    assert st.run_signal_rule(CFG, b.index[-1], b, tmp_path, Strategy)["decisions_changed_since_recorded"] == []

    class Other:
        generate_signals = staticmethod(lambda x: pd.Series(0.0, x.index))
    flagged = st.run_signal_rule(CFG, b.index[-1], b, tmp_path, Other)["decisions_changed_since_recorded"]
    assert flagged and pd.read_csv(tmp_path / "signals.csv", index_col="date", parse_dates=True)["target"].equals(stored["target"])


def test_waiting_before_start_and_stale_data(tmp_path):
    b = bars()
    assert st.run_signal_rule(CFG | {"start": "2030-01-02"}, b.index[-1], b, tmp_path, Strategy)["state"] == "waiting"
    from core.paper_runner import DataNotReady
    with pytest.raises(DataNotReady):
        st.run_signal_rule(CFG, b.index[-1] + pd.Timedelta(days=3), b, tmp_path, Strategy)


def test_screen_counts_passers_and_alerts_only_at_ten_percent():
    cells = [{"hypothesis": 1, "cell": f"X{i}", "IS": "supports" if i < 24 else "contradicts",
              "OOS": "supports" if i < 12 else "contradicts", "OLD": "supports" if i < 38 else "contradicts"} for i in range(100)]
    r = screen.screen(cells)
    assert r["cells"] == 100 and len(r["passers"]) == 12 and r["expected_by_luck"] == pytest.approx(100 * .24 * .12 * .38)
    assert r["fdr"] == pytest.approx(r["expected_by_luck"] / 12) and r["alert"]            # about 9%
    sets = {"IS": set(range(26)), "OOS": {0} | set(range(26, 38)), "OLD": {0} | set(range(38, 78))}      # the real run: 26, 13, 41 of 108, one in all three
    real = [{"hypothesis": 1, "cell": f"X{i}", **{e: "supports" if i in sets[e] else "contradicts" for e in sets}} for i in range(108)]
    out = screen.screen(real)
    assert out["passers"] == [(1, "X0")] and out["expected_by_luck"] == pytest.approx(1.19, abs=0.01) and out["fdr"] == 1.0 and not out["alert"]
    assert screen.screen([{"hypothesis": 1, "cell": "A", "IS": "supports", "OOS": None, "OLD": "supports"}])["cells"] == 0
