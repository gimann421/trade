import numpy as np
import pandas as pd
import pytest

from core.backtest import ROOT, load_strategy, run_backtest

NAMES = {
    14: "dd_gated_sma_exit", 15: "trend_vol_throttle", 16: "cppi_cushion",
    17: "bollinger_stepaside", 18: "mean_reversion_z50", 19: "volume_shock_reversal",
    20: "good_bad_vol_filter", 21: "squeeze_release", 22: "vol_peak_rebound",
}


def strategy(name):
    return load_strategy(ROOT / "strategies" / f"{name}_v1.py")


def bars_from_close(close, volume=None, wiggle=0.002):
    close = np.asarray(close, float)
    idx = pd.bdate_range("2018-01-01", periods=len(close))
    return pd.DataFrame({
        "open": close, "high": close * (1 + wiggle), "low": close * (1 - wiggle), "close": close,
        "volume": np.full(len(close), 1000.0) if volume is None else np.asarray(volume, float),
    }, index=idx)


def random_bars(n=1500, seed=0):
    rng = np.random.default_rng(seed)
    close = 100 * np.cumprod(1 + rng.normal(0.0003, 0.01, n))
    return bars_from_close(close, volume=rng.uniform(500, 1500, n), wiggle=0.004)


@pytest.mark.parametrize("hid", NAMES)
def test_weights_valid_and_no_lookahead(hid):
    module = strategy(NAMES[hid])
    bars = random_bars()
    weights = module.generate_signals(bars)
    assert weights.index.equals(bars.index) and not weights.isna().any()
    assert weights.between(0, 1).all()
    run_backtest(bars, module.generate_signals)  # raises if signals change when later bars are added


@pytest.mark.parametrize("hid", [15, 16])
def test_fractional_weights_stay_on_quarter_grid(hid):
    weights = strategy(NAMES[hid]).generate_signals(random_bars(seed=3))
    assert np.allclose(weights * 4, np.round(weights * 4))


@pytest.mark.parametrize("name, warmup", [("squeeze_release", 260), ("vol_peak_rebound", 520)])
def test_event_strategies_flat_during_warmup(name, warmup):
    weights = strategy(name).generate_signals(random_bars())
    assert (weights.iloc[:warmup] == 0).all()


# Bars before every indicator exists: SMA200 / 252-day high / 20-day z / 252-day median of 20-day vol.
WARMUP = {14: 251, 15: 199, 16: 251, 17: 19, 20: 271}


@pytest.mark.parametrize("hid, bars_needed", WARMUP.items())
def test_derisking_strategies_fully_invested_during_warmup(hid, bars_needed):
    weights = strategy(NAMES[hid]).generate_signals(random_bars())
    assert (weights.iloc[:bars_needed] == 1).all()


def test_dd_gated_exit_steps_down_then_re_enters_slowly():
    close = [100.0] * 260 + [88.0] * 3 + [78.0] * 3 + [101.0] * 3
    weights = strategy("dd_gated_sma_exit").generate_signals(bars_from_close(close)).to_numpy()
    assert weights[259] == 1.0
    assert weights[260] == 0.5            # below the SMA and 12% under the high
    assert weights[263] == 0.0            # 22% under the high
    assert weights[266] == 0.5            # back above the SMA: half weight first
    assert weights[267] == 1.0            # then full once within 5% of the high


def test_cppi_cuts_immediately_but_only_re_risks_above_trend():
    close = [100.0] * 260 + [85.0] * 3 + [90.0] * 3 + [105.0] * 3
    weights = strategy("cppi_cushion").generate_signals(bars_from_close(close)).to_numpy()
    assert weights[259] == 1.0
    assert weights[260] == 0.5            # cushion (85 - 70) / 85 = 0.176 -> 4c = 0.71 -> 0.5
    assert weights[263] == 0.5            # 90 would allow 0.75 but is below the 100-day SMA
    assert weights[266] == 1.0            # 105 is above the SMA: re-risk to full


def test_bollinger_stepaside_hysteresis():
    close = [100.0 + 0.1 * (i % 2) for i in range(60)] + [110.0, 105.0, 99.0]
    weights = strategy("bollinger_stepaside").generate_signals(bars_from_close(close)).to_numpy()
    assert weights[59] == 1.0
    assert weights[60] == 0.0             # z far above 2
    assert weights[61] == 0.0             # still above the mean: stay out
    assert weights[62] == 1.0             # back below the mean


def test_z50_holds_at_most_thirty_days():
    close = [100.0 + 0.1 * (i % 2) for i in range(80)] + [90.0] * 60
    weights = strategy("mean_reversion_z50").generate_signals(bars_from_close(close)).to_numpy()
    assert weights[79] == 0.0 and weights[80] == 1.0
    assert weights[80:110].tolist() == [1.0] * 30      # 30 bars = 30 return days
    assert weights[110] == 0.0 and weights[111] == 0.0  # exit bar flat; z has recovered past -1.5


def test_z50_exits_at_the_mean():
    close = [100.0 + 0.1 * (i % 2) for i in range(80)] + [90.0, 100.2, 100.0, 100.0]
    weights = strategy("mean_reversion_z50").generate_signals(bars_from_close(close)).to_numpy()
    assert weights[80] == 1.0 and weights[81] == 0.0


def test_volume_shock_needs_volume_and_holds_five_days():
    rng = np.random.default_rng(5)
    close = list(100 * np.cumprod(1 + rng.normal(0, 0.002, 60)))
    for _ in range(3):
        close.append(close[-1] * 0.985)
    close += [close[-1]] * 12
    volume = [1000.0] * len(close)
    quiet = strategy("volume_shock_reversal").generate_signals(bars_from_close(close, volume)).to_numpy()
    assert quiet.sum() == 0                              # big drop on normal volume: no signal
    volume[62] = 3000.0
    loud = strategy("volume_shock_reversal").generate_signals(bars_from_close(close, volume)).to_numpy()
    assert loud[61] == 0.0
    assert loud[62:67].tolist() == [1.0] * 5 and loud[67] == 0.0   # exactly 5 return days
