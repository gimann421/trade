from core.risk import AccountState, ProposedOrder, RiskLimits, check_order

LIMITS = RiskLimits(max_position_pct=5.0, max_gross_exposure_pct=50.0, max_open_positions=3,
                    max_order_notional=5000, max_daily_loss_pct=2.0, allow_short=False)


def state(positions=None, equity=100_000, day_start=100_000):
    return AccountState(equity, day_start, positions or {})


def buy(symbol="SPY", qty=10, price=400):
    return ProposedOrder(symbol, "buy", qty, price)


def sell(symbol="SPY", qty=10, price=400):
    return ProposedOrder(symbol, "sell", qty, price)


def test_small_buy_passes():
    assert check_order(buy(), state(), LIMITS) == []


def test_order_notional_cap():
    assert any("max_order_notional" in v for v in check_order(buy(qty=20), state(), LIMITS))


def test_position_cap():
    # $4,000 already held + $4,000 more = $8,000 > 5% of $100k
    assert any("of equity" in v for v in check_order(buy(), state({"SPY": 4000}), LIMITS))


def test_gross_exposure_cap():
    held = {"A": 5000, "B": 5000, "SPY": 0}
    limits = RiskLimits(5.0, 12.0, 10, 5000, 2.0, False)
    assert any("gross exposure" in v for v in check_order(buy(), state(held), limits))


def test_max_open_positions():
    held = {"A": 1000, "B": 1000, "C": 1000}
    assert any("max_open_positions" in v for v in check_order(buy(), state(held), LIMITS))
    # adding to an existing position doesn't open a new one
    assert check_order(buy("A", qty=1), state(held), LIMITS) == []


def test_daily_loss_blocks_new_risk_but_allows_exits():
    down = state({"SPY": 4000}, equity=97_000, day_start=100_000)
    assert any("max_daily_loss_pct" in v for v in check_order(buy("QQQ"), down, LIMITS))
    assert check_order(sell(qty=5), down, LIMITS) == []


def test_short_blocked():
    assert any("short" in v for v in check_order(sell(), state(), LIMITS))
    assert any("short" in v for v in check_order(sell(qty=20), state({"SPY": 4000}), LIMITS))


def test_reducing_exit_allowed_even_when_large():
    big = state({"SPY": 40_000}, equity=100_000)
    assert check_order(sell(qty=50), big, LIMITS) == []


def test_bad_inputs():
    assert check_order(ProposedOrder("SPY", "hold", 1, 1), state(), LIMITS)
    assert check_order(buy(qty=0), state(), LIMITS)
    assert check_order(buy(), state(equity=0), LIMITS)
