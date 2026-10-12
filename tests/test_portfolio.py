import numpy as np
import pandas as pd
import pytest

from core.backtest import run_backtest
from core.config import ROOT
from core.portfolio import (align, check_no_lookahead, load_portfolio_strategy, month_ends,
                            run_portfolio_backtest, simulate, targets_from)


def make_bars(n=300, seed=0, symbols=("SPY", "TLT", "GLD")):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2020-01-01", periods=n)
    out = {}
    for i, s in enumerate(symbols):
        close = 100 * np.cumprod(1 + rng.normal(0.0003 * (i + 1), 0.01, n))
        out[s] = pd.DataFrame({"open": close, "high": close, "low": close, "close": close,
                               "volume": 1e6}, index=idx)
    return out


def weights_on(bars, rows: dict, default=np.nan):
    """DataFrame of weights: rows maps position -> weights list; everything else NaN."""
    idx = next(iter(bars.values())).index
    frame = pd.DataFrame(default, index=idx, columns=list(bars))
    for pos, w in rows.items():
        frame.iloc[pos] = w
    return frame


def close_of(bars):
    return pd.DataFrame({s: b["close"] for s, b in bars.items()})


def test_single_asset_fully_invested_matches_single_symbol_backtester():
    bars = make_bars()
    one = {"SPY": bars["SPY"]}
    ours = run_portfolio_backtest(one, lambda b: weights_on(b, {0: [1.0]}), cost_bps=0)
    ref = run_backtest(bars["SPY"], lambda b: pd.Series(1.0, index=b.index), cost_bps=0)
    assert ours["strategy"]["total_return"] == pytest.approx(ref["strategy"]["total_return"])
    assert ours["strategy"]["max_drawdown"] == pytest.approx(ref["strategy"]["max_drawdown"])


def test_buy_and_hold_lets_weights_drift():
    bars = make_bars(symbols=("SPY", "TLT"))
    close = close_of(bars)
    run = simulate(close, weights_on(bars, {0: [0.5, 0.5]}), cost_bps=0)
    growth = close.iloc[-1] / close.iloc[0]
    assert (1 + run["returns"]).prod() == pytest.approx(0.5 * growth["SPY"] + 0.5 * growth["TLT"])
    assert run["traded"].iloc[1:].sum() == 0          # no rebalancing, so no trading after day 0


def test_costs_charged_on_trades_against_drifted_holdings():
    bars = make_bars(symbols=("SPY", "TLT"))
    close = close_of(bars)
    rows = {0: [0.5, 0.5], 100: [0.5, 0.5]}
    run = simulate(close, weights_on(bars, rows), cost_bps=10)
    ret = close.pct_change().fillna(0.0)
    value = (1 + ret.iloc[1:101]).prod()
    drifted = 0.5 * value / (0.5 * value).sum()
    expected = abs(0.5 - drifted["SPY"]) + abs(0.5 - drifted["TLT"])
    assert run["traded"].iloc[0] == pytest.approx(1.0)                 # 0 -> 100% invested
    assert run["traded"].iloc[100] == pytest.approx(expected)          # only the drift is traded
    assert run["traded"].iloc[100] < 0.1


def test_cash_earns_nothing_by_default_and_the_given_rate_otherwise():
    bars = make_bars()
    close = close_of(bars)
    idle = simulate(close, weights_on(bars, {}), cost_bps=5)
    assert (idle["returns"] == 0).all() and (idle["held"] == 0).all()
    earning = simulate(close, weights_on(bars, {}), cost_bps=5, cash_return=0.0252)
    assert (1 + earning["returns"]).prod() == pytest.approx(1.0252 ** (len(close) / 252))


@pytest.mark.parametrize("bad, message", [
    ([1.2, 0.0, 0.0], "in \\[0, 1\\]"),
    ([-0.1, 0.5, 0.5], "in \\[0, 1\\]"),
    ([0.6, 0.6, 0.0], "sum to at most 1"),
    ([0.5, np.nan, 0.5], "mixes NaN"),
])
def test_invalid_weights_rejected(bad, message):
    bars = make_bars()
    with pytest.raises(ValueError, match=message):
        targets_from(bars, lambda b: weights_on(b, {5: bad}))


def test_columns_must_match_symbols():
    bars = make_bars()
    with pytest.raises(ValueError, match="exactly the columns"):
        targets_from(bars, lambda b: weights_on({"SPY": b["SPY"]}, {0: [1.0]}))


def test_sparse_output_means_no_trade():
    bars = make_bars()
    idx = bars["SPY"].index
    sparse = pd.DataFrame([[1.0, 0.0, 0.0]], index=idx[[3]], columns=list(bars))
    targets = targets_from(bars, lambda b: sparse)
    assert targets.iloc[3].tolist() == [1.0, 0.0, 0.0] and targets.drop(idx[3]).isna().all().all()


def test_future_peeking_strategy_rejected():
    bars = make_bars()

    def cheat(b):
        close = close_of(b)
        best = close.pct_change().shift(-1).rank(axis=1).eq(3).astype(float)   # tomorrow's winner
        return best

    with pytest.raises(ValueError, match="future data"):
        check_no_lookahead(bars, cheat)


def test_window_scores_a_slice_with_holdings_carried_in():
    bars = make_bars()
    gen = lambda b: weights_on(b, {0: [1 / 3, 1 / 3, 1 / 3]})
    idx = bars["SPY"].index
    window = run_portfolio_backtest(bars, gen, cost_bps=5, start=str(idx[100].date()), end=str(idx[199].date()))
    full = run_portfolio_backtest(bars, gen, cost_bps=5)
    assert window["days"] == 100 and window["start"] == str(idx[100].date())
    assert window["strategy"]["trades"] == 0 and full["strategy"]["trades"] == 1   # the entry trade is outside
    assert window["strategy"]["exposure"] == pytest.approx(1.0)
    with pytest.raises(ValueError, match="no bars"):
        run_portfolio_backtest(bars, gen, start="2030-01-01")


def test_benchmarks_present_and_equal_weight_hold_matches_hand_calculation():
    bars = make_bars()
    result = run_portfolio_backtest(bars, lambda b: weights_on(b, {}), cost_bps=0)
    assert set(result["benchmarks"]) == {"equal_weight_hold", "equal_weight_monthly",
                                         "inverse_vol_monthly", "sixty_forty"}
    growth = close_of(bars).iloc[-1] / close_of(bars).iloc[0]
    assert result["benchmarks"]["equal_weight_hold"]["total_return"] == pytest.approx(growth.mean() - 1)
    no_bonds = run_portfolio_backtest({"SPY": bars["SPY"], "GLD": bars["GLD"]}, lambda b: weights_on(b, {}))
    assert "sixty_forty" not in no_bonds["benchmarks"]


def test_monthly_benchmarks_only_trade_at_month_ends():
    bars = make_bars()
    close = close_of(bars)
    from core.portfolio import benchmark_targets
    rows = benchmark_targets(bars)["equal_weight_monthly"].dropna().index
    expected = set(close.index[month_ends(close.index)]) | {close.index[0]}
    assert set(rows) == expected
    sixty = benchmark_targets(bars)["sixty_forty"].dropna()
    assert (sixty["SPY"] == 0.6).all() and (sixty["TLT"] == 0.4).all() and (sixty["GLD"] == 0).all()


def test_align_keeps_common_dates_only():
    a, b = make_bars(10)["SPY"], make_bars(10)["TLT"].iloc[2:]
    both = align({"SPY": a, "TLT": b})
    assert len(both["SPY"]) == len(both["TLT"]) == 8


def test_load_portfolio_strategy_checks_name_version_and_function(tmp_path):
    ok = tmp_path / "mix_v1.py"
    ok.write_text("VERSION = 1\ndef generate_weights(b): pass\n")
    assert load_portfolio_strategy(ok).STRATEGY_NAME == "mix"
    for name, body, message in [("Mix.py", "VERSION = 1\ndef generate_weights(b): pass\n", "_v<N>"),
                                ("mix_v2.py", "VERSION = 1\ndef generate_weights(b): pass\n", "VERSION must be 2"),
                                ("mix_v1.py", "VERSION = 1\n", "generate_weights")]:
        path = tmp_path / "other" / name
        path.parent.mkdir(exist_ok=True)
        path.write_text(body)
        with pytest.raises(ValueError, match=message):
            load_portfolio_strategy(path)


def test_signal_only_symbol_informs_the_strategy_but_is_not_held_or_benchmarked():
    bars = make_bars(symbols=("SPY", "TLT", "AGG"))
    seen = {}

    def strategy(b):
        seen["symbols"] = list(b)
        return weights_on(b, {0: [0.5, 0.5, 0.0]})

    result = run_portfolio_backtest(bars, strategy, cost_bps=0, signal_only=("AGG",))
    assert seen["symbols"] == ["SPY", "TLT", "AGG"]
    assert result["symbols"] == ["SPY", "TLT"] and result["signal_only"] == ["AGG"]
    growth = close_of(bars).iloc[-1] / close_of(bars).iloc[0]
    # equal_weight_hold covers SPY and TLT only
    assert result["benchmarks"]["equal_weight_hold"]["total_return"] == pytest.approx(
        (growth["SPY"] + growth["TLT"]) / 2 - 1)
    with pytest.raises(ValueError, match="signal-only"):
        run_portfolio_backtest(bars, lambda b: weights_on(b, {0: [0.4, 0.4, 0.2]}), signal_only=("AGG",))


def test_inverse_vol_benchmark_ignores_cash_assets():
    from core.portfolio import benchmark_targets
    bars = make_bars(symbols=("SPY", "TLT"))
    idx = bars["SPY"].index
    flat = 100 * (1 + 1e-5 * np.arange(len(idx)))               # almost no volatility
    bars["BIL"] = pd.DataFrame({"open": flat, "high": flat, "low": flat, "close": flat,
                                "volume": 1e6}, index=idx)
    with_cash = benchmark_targets(bars)["inverse_vol_monthly"].dropna()
    without = benchmark_targets(bars, cash_symbols=("BIL",))["inverse_vol_monthly"].dropna()
    assert with_cash["BIL"].min() > 0.9                       # nearly all weight in the quiet asset
    assert (without["BIL"] == 0).all() and without.sum(axis=1).round(9).eq(1).all()


def test_portfolio_placebo_high_for_foresight_and_middling_for_random_timing():
    from core.portfolio import portfolio_placebo_percentile
    bars = make_bars(n=900, seed=4)
    close = close_of(bars)
    ret = close.pct_change().fillna(0.0)

    # A position that knows tomorrow's best asset: cheating (the engine's look-ahead check would
    # reject it), so build the targets directly to give the placebo a clear edge to detect.
    best = ret.shift(-1).fillna(0.0).idxmax(axis=1)
    foresight = pd.DataFrame(0.0, close.index, close.columns)
    for date, symbol in best.items():
        foresight.loc[date, symbol] = 1.0
    run_f = simulate(close, foresight, cost_bps=0)
    assert portfolio_placebo_percentile(close, run_f, cost_bps=0) > 0.99

    rng = np.random.default_rng(1)
    random_w = pd.DataFrame(rng.dirichlet(np.ones(3), size=len(close)) * (rng.random((len(close), 1)) < 0.7),
                            close.index, close.columns)
    run_r = simulate(close, random_w, cost_bps=0)
    assert 0.02 < portfolio_placebo_percentile(close, run_r, cost_bps=0, seed=3) < 0.98
    with pytest.raises(ValueError, match="too short"):
        portfolio_placebo_percentile(close, run_r, start=str(close.index[0].date()),
                                     end=str(close.index[300].date()), cost_bps=0)


def test_run_holdings_rebuild_the_engine_returns():
    bars = make_bars(n=400, seed=2)
    gen = lambda b: weights_on(b, {0: [0.4, 0.3, 0.3], 60: [0.2, 0.2, 0.2], 120: [0.5, 0.5, 0.0]})
    from core.portfolio import prepare
    _, close, run = prepare(bars, gen, cost_bps=5)
    rebuilt = (run["weights"] * close.pct_change().fillna(0.0)).sum(axis=1) - run["traded"] * 5 / 10_000
    assert np.allclose(rebuilt, run["returns"])
    assert np.allclose(run["weights"].sum(axis=1) + run["cash"], 1.0)


def test_month_ends_follow_the_calendar_not_the_data():
    from core.market_calendar import trading_days
    idx = trading_days("2024-01-01", "2024-12-31")             # real sessions: no bar on holidays
    flags = month_ends(idx)
    last_days = idx[flags]
    assert len(last_days) == 12 and str(last_days[0].date()) == "2024-01-31"
    assert str(last_days[-1].date()) == "2024-12-31"
    # truncating mid-month must not invent a month-end at the new last bar
    assert not month_ends(idx[idx <= "2024-03-14"])[-1]
    # a month ending on a holiday weekend (Fri 2024-03-29 is Good Friday): Thursday is the last session
    spring = idx[(idx >= "2024-03-25") & (idx <= "2024-04-03")]
    assert str(spring[month_ends(spring)][0].date()) == "2024-03-28"
