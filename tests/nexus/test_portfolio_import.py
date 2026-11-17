from datetime import timezone
from decimal import Decimal

import pytest

from nexus.accounting import actual_state, load_snapshot
from nexus.domain import LedgerKind
from nexus.errors import LaunchBoundaryViolation, NexusError
from nexus.portfolio_import import assert_schwab_read_only, parse_holdings_csv, import_holdings_csv

CSV = """Symbol,Quantity,Cost Basis,Market Value
AAPL,10,"$1,500.00",1900
MSFT,2.5,,1000
Cash & Cash Investments,--,--,"$1,234.56"
Account Total,--,--,4134.56
"""


def test_parse_csv():
    cash, hold, est = parse_holdings_csv(CSV)
    assert cash == {"USD": "1234.56"} and hold["AAPL"] == {"quantity": "10", "cost_basis": "1500.00"}
    assert est == ["MSFT.cost_basis"]


@pytest.mark.parametrize("bad", ["", "Foo,Bar\n1,2", "Symbol,Quantity\nAAPL,-3", "Symbol,Quantity\nAAPL,1\nAAPL,2",
                                 "Symbol,Quantity\nbad sym!,1", "Symbol,Quantity\nAAPL,", "Symbol,Quantity\nAAPL,abc"])
def test_bad_csv_rejected(bad):
    with pytest.raises(NexusError):
        parse_holdings_csv(bad)


def test_import_creates_confirmed_snapshot_and_flags_estimates(store, clock):
    acct = store.create_account(LedgerKind.ACTUAL, "schwab").account_id
    sid = import_holdings_csv(store, acct, CSV, clock.now, "Schwab positions export (CSV)", "Garret")
    st = actual_state(store, acct)
    assert st.cash == Decimal("1234.56") and st.positions["EQ:US:AAPL"] == 10
    est = load_snapshot(store, sid)["estimated_fields"]
    assert "MSFT.cost_basis" in est and "AAPL.instrument_details" in est
    assert store.get_instrument("EQ:US:AAPL").capability_tier.value == "R1"


def test_import_without_auto_register_refuses_unknown(store, clock):
    acct = store.create_account(LedgerKind.ACTUAL, "schwab").account_id
    with pytest.raises(NexusError):
        import_holdings_csv(store, acct, CSV, clock.now, "x", "Garret", auto_register=False)


def test_missing_cash_row_is_flagged():
    _, _, est = parse_holdings_csv("Symbol,Quantity\nAAPL,1")
    assert "cash" in est


@pytest.mark.parametrize("method,url", [
    ("POST", "https://api.schwabapi.com/trader/v1/accounts/ABC123/orders"),
    ("GET", "https://api.schwabapi.com/trader/v1/accounts/ABC123/orders"),
    ("DELETE", "https://api.schwabapi.com/trader/v1/accounts"),
    ("PUT", "https://api.schwabapi.com/trader/v1/accounts"),
    ("GET", "https://api.schwabapi.com/trader/v1/accounts/ABC/transactions"),
    ("GET", "https://evil.com/trader/v1/accounts"),
    ("GET", "http://api.schwabapi.com/trader/v1/accounts"),
    ("GET", "https://api.schwabapi.com/trader/v1/accounts/ABC/previewOrder"),
])
def test_schwab_write_and_other_endpoints_refused(method, url):
    with pytest.raises(LaunchBoundaryViolation):
        assert_schwab_read_only(method, url)


@pytest.mark.parametrize("url", ["https://api.schwabapi.com/trader/v1/accounts", "https://api.schwabapi.com/trader/v1/accounts/ABC123",
                                 "https://api.schwabapi.com/trader/v1/accounts/ABC123/positions"])
def test_schwab_read_allowlist(url):
    assert_schwab_read_only("get", url)
