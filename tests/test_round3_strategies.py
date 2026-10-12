import numpy as np
import pandas as pd
import pytest

from core.backtest import ROOT, load_strategy, run_backtest
from core.portfolio import load_portfolio_strategy, month_ends, run_portfolio_backtest, targets_from


def strategy(name, portfolio=False):
    path = ROOT / "strategies" / f"{name}_v1.py"
    return load_portfolio_strategy(path) if portfolio else load_strategy(path)


def trending_bars(growth: dict, n=420, seed=0, noise=0.0):
    """Daily bars where each symbol compounds at its own daily rate (optionally with noise)."""
    idx = pd.bdate_range("2018-01-01", periods=n)
    rng = np.random.default_rng(seed)
    out = {}
    for symbol, g in growth.items():
        close = 100 * np.cumprod(1 + g + noise * rng.normal(size=n))
        out[symbol] = pd.DataFrame({"open": close, "high": close, "low": close, "close": close,
                                    "volume": 1e6}, index=idx)
    return out


def rows(weights):
    return weights.dropna(how="all")


# --- portfolio strategies ------------------------------------------------------------------

def test_dual_momentum_picks_the_top_two_and_falls_back_to_cash():
    module = strategy("dual_momentum", portfolio=True)
    risky = ["A", "B", "C", "D"]
    growth = {"A": 0.0010, "B": 0.0006, "C": -0.0004, "D": -0.0008, "BIL": 0.0001}
    w = rows(module.generate_weights(trending_bars(growth), risky=risky))
    month_end_idx = trending_bars(growth)["A"].index[month_ends(trending_bars(growth)["A"].index)]
    assert list(w.index) == list(month_end_idx)                                 # month-ends only
    assert (w.iloc[:11] == [0, 0, 0, 0, 1.0]).all().all()                      # before 253 closes: all BIL
    last = w.iloc[-1]
    assert last.to_dict() == {"A": 0.5, "B": 0.5, "C": 0.0, "D": 0.0, "BIL": 0.0}
    # only A beats BIL: B's half goes to cash
    one = rows(module.generate_weights(trending_bars({**growth, "B": -0.0002}), risky=risky)).iloc[-1]
    assert one.to_dict() == {"A": 0.5, "B": 0.0, "C": 0.0, "D": 0.0, "BIL": 0.5} or \
        one["A"] == 0.5 and one["BIL"] == 0.5 and one.sum() == pytest.approx(1.0)
    # nothing beats BIL: everything in cash
    none = rows(module.generate_weights(
        trending_bars({"A": -0.0002, "B": -0.0003, "C": -0.0004, "D": -0.0008, "BIL": 0.0001}), risky=risky)).iloc[-1]
    assert none["BIL"] == 1.0


def test_canary_momentum_cash_fraction_follows_bad_canaries():
    module = strategy("canary_momentum", portfolio=True)
    risky = ["A", "B", "C", "D"]
    base = {"A": 0.0010, "B": 0.0008, "C": 0.0006, "D": 0.0004, "BIL": 0.0001}
    kwargs = dict(risky=risky, canaries=("A", "CAN"), top=2)
    cases = [({"CAN": 0.0005}, 0.0), ({"CAN": -0.001}, 0.5), ({"CAN": -0.001, "A": -0.0005}, 1.0)]
    for extra, cash in cases:
        w = rows(module.generate_weights(trending_bars({**base, **extra}), **kwargs)).iloc[-1]
        assert w["BIL"] == pytest.approx(cash)
        assert w["CAN"] == 0 and w.sum() == pytest.approx(1.0)
        if cash < 1.0:
            held = w[risky]
            assert (held > 0).sum() == 2 and held.max() == pytest.approx((1 - cash) / 2)
    early = rows(module.generate_weights(trending_bars({**base, "CAN": 0.0005}), **kwargs)).iloc[0]
    assert early["BIL"] == 1.0


def test_breadth_paa_cash_fraction_and_selection():
    module = strategy("breadth_paa", portfolio=True)
    risky = ["A", "B", "C", "D"]
    up = {"A": 0.0010, "B": 0.0008, "C": 0.0006, "D": 0.0004, "BIL": 0.0001}
    w = rows(module.generate_weights(trending_bars(up), risky=risky)).iloc[-1]
    assert w.to_dict() == {"A": 0.5, "B": 0.5, "C": 0.0, "D": 0.0, "BIL": 0.0}      # all up: BF = 0, top 2
    half = {**up, "C": -0.001, "D": -0.001}                                           # n = 2 of N = 4: BF = 1
    assert rows(module.generate_weights(trending_bars(half), risky=risky)).iloc[-1]["BIL"] == pytest.approx(1.0)
    one_down = {**up, "D": -0.001}                                                    # n = 3: BF = 0.5
    w = rows(module.generate_weights(trending_bars(one_down), risky=risky)).iloc[-1]
    assert w["BIL"] == pytest.approx(0.5) and w["A"] == pytest.approx(0.25) and w["B"] == pytest.approx(0.25)


@pytest.mark.parametrize("name, kwargs, signal_only", [
    ("dual_momentum", dict(risky=["A", "B", "C"]), ()),
    ("canary_momentum", dict(risky=["A", "B", "C"], canaries=("A", "CAN"), top=2), ("CAN",)),
    ("breadth_paa", dict(risky=["A", "B", "C"]), ()),
])
def test_portfolio_strategies_run_without_lookahead(name, kwargs, signal_only):
    module = strategy(name, portfolio=True)
    bars = trending_bars({"A": 0.0006, "B": 0.0002, "C": -0.0001, "BIL": 0.0001, "CAN": 0.0003},
                         n=700, seed=5, noise=0.01)
    bars = {s: b for s, b in bars.items() if s != "CAN" or signal_only}
    result = run_portfolio_backtest(bars, lambda b: module.generate_weights(b, **kwargs),
                                    signal_only=signal_only, cash_symbols=("BIL",))
    assert result["strategy"]["trades"] > 0 and "CAN" not in result["symbols"]
    assert targets_from(bars, lambda b: module.generate_weights(b, **kwargs), signal_only).notna().any().any()


# --- overnight signals ---------------------------------------------------------------------

def overnight_bars(on, intraday, n=None):
    """Bars with prescribed overnight and intraday log returns."""
    on, intraday = np.asarray(on, float), np.asarray(intraday, float)
    close = 100.0
    opens, closes = [], []
    for o, i in zip(on, intraday):
        open_ = close * np.exp(o)
        close = open_ * np.exp(i)
        opens.append(open_)
        closes.append(close)
    idx = pd.bdate_range("2018-01-01", periods=len(on))
    c, o = np.array(closes), np.array(opens)
    return pd.DataFrame({"open": o, "high": np.maximum(o, c), "low": np.minimum(o, c), "close": c,
                         "volume": 1e6}, index=idx)


def test_overnight_tilt_halves_after_a_strong_overnight_run_then_restores():
    rng = np.random.default_rng(1)
    n = 280 + 20 + 120
    on = rng.normal(0, 0.002, n)
    on[300:320] += 0.01                                    # 20 days of strong overnight gains
    bars = overnight_bars(on, rng.normal(0, 0.002, n))
    w = strategy("overnight_tilt").generate_signals(bars)
    assert (w.iloc[:270] == 1).all()
    assert w.iloc[300:320].min() == 0.5 and set(w.unique()) == {0.5, 1.0}
    assert w.iloc[-1] == 1.0                               # the run has aged out, rank back below 0.60


def test_overnight_trend_filter_and_close_to_close_control():
    n = 400
    on = np.r_[np.full(250, 0.001), np.full(150, -0.001)]
    intraday = np.r_[np.full(250, 0.0), np.full(150, 0.003)]    # prices keep rising intraday
    bars = overnight_bars(on, intraday)
    overnight = strategy("overnight_trend").generate_signals(bars)
    control = strategy("overnight_trend").generate_signals(bars, component="close")
    assert (overnight.iloc[:126] == 1).all() and overnight.iloc[100] == 1
    assert overnight.iloc[-1] == 0.0                       # the overnight sum turned negative
    assert control.iloc[-1] == 1.0                         # close-to-close still trends up
    with pytest.raises(ValueError, match="component"):
        strategy("overnight_trend").generate_signals(bars, component="intraday")


def test_gap_fade_washout_holds_exactly_three_days_and_needs_a_gap_up():
    rng = np.random.default_rng(2)
    n = 160
    on, intraday = rng.normal(0, 0.002, n), rng.normal(0, 0.002, n)
    on[100], intraday[100] = 0.01, -0.03                   # gap up, then a big fade
    on[130], intraday[130] = -0.01, -0.03                  # big fade but no gap up: no trigger
    w = strategy("gap_fade_washout").generate_signals(overnight_bars(on, intraday)).to_numpy()
    assert w[100:103].tolist() == [1.0, 1.0, 1.0] and w[103] == 0.0 and w[99] == 0.0
    assert w[130] == 0.0 and w.sum() == 3.0
    early_on, early_id = np.zeros(n), np.zeros(n)
    early_on[30], early_id[30] = 0.01, -0.03
    assert strategy("gap_fade_washout").generate_signals(overnight_bars(early_on, early_id)).sum() == 0


@pytest.mark.parametrize("name", ["overnight_tilt", "overnight_trend", "gap_fade_washout"])
def test_overnight_strategies_valid_and_no_lookahead(name):
    rng = np.random.default_rng(3)
    n = 900
    bars = overnight_bars(rng.normal(0, 0.003, n), rng.normal(0, 0.008, n))
    module = strategy(name)
    weights = module.generate_signals(bars)
    assert weights.between(0, 1).all() and not weights.isna().any()
    run_backtest(bars, module.generate_signals)


# --- calendar windows ----------------------------------------------------------------------

def test_halloween_enters_at_last_october_close_and_exits_at_last_april_close():
    idx = pd.bdate_range("2023-01-02", "2025-12-31")
    bars = pd.DataFrame({"close": 100.0}, index=idx)
    w = strategy("halloween").generate_signals(bars)
    at = lambda d: w[pd.Timestamp(d)]
    assert at("2023-10-30") == 0 and at("2023-10-31") == 1 and at("2023-11-01") == 1
    assert at("2024-04-29") == 1 and at("2024-04-30") == 0 and at("2024-05-01") == 0
    assert at("2024-06-14") == 0 and at("2024-02-14") == 1
    assert at("2023-01-03") == 1                           # the winter in progress when the data starts


def test_earnings_season_window_runs_from_day_eleven_to_month_end():
    idx = pd.bdate_range("2025-01-02", "2025-12-31")
    bars = pd.DataFrame({"close": 100.0}, index=idx)
    w = strategy("earnings_season").generate_signals(bars)
    at = lambda d: w[pd.Timestamp(d)]
    # October 2025: trading day 10 is Tue the 14th (Columbus Day is a trading day)
    assert at("2025-10-13") == 0 and at("2025-10-14") == 1 and at("2025-10-30") == 1
    assert at("2025-10-31") == 0 and at("2025-11-14") == 0 and at("2025-12-15") == 0
    # January 2025: day 10 is Jan 15 (the unscheduled Jan 9 closure is not a calendar holiday, so it
    # counts as day 6; Jan 1 and Jan 20 are holidays)
    assert at("2025-01-14") == 0 and at("2025-01-15") == 1 and at("2025-01-30") == 1
    assert at("2025-01-31") == 0
    # a full year: four windows of roughly a third of a month each
    assert 0.12 < w.mean() < 0.22
