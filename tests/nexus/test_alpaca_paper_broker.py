from datetime import datetime, timezone

import pytest

from nexus.accounting import record_entry
from nexus.brokers.alpaca_paper import AlpacaPaperBroker, urllib_transport
from nexus.domain import AssetClass, CapabilityTier, Instrument, LedgerKind
from nexus.errors import LaunchBoundaryViolation, NexusError, SecretError, SystemHalted
from nexus.orders import OrderRequest, propose_order
from nexus.secrets import Secret
from tests.nexus.test_orders_simulator import IID, SESS, decide_at, load, req

K, S = Secret("k", "keyvalue123456"), Secret("s", "secretvalue123456")


@pytest.fixture
def setup(store, clock):
    store.register_instrument(Instrument(IID, {"alpaca": "AAPL"}, AssetClass.EQUITY, "USD", "America/New_York", capability_tier=CapabilityTier.R2))
    acct = store.create_account(LedgerKind.PAPER_SLEEVE, "paper").account_id
    record_entry(store, acct, "DEPOSIT", clock.now, cash_delta="100000")
    load(store, clock, 5)
    now = decide_at(SESS[4]); clock.now = now
    return store, acct, now


def test_submit_posts_only_to_paper_endpoint(setup):
    store, acct, now = setup
    calls = []
    def t(method, url, headers, body):
        calls.append((method, url, body))
        return {"id": "broker-123"}
    oid = propose_order(store, req(acct, mode="paper_broker"), now)
    assert AlpacaPaperBroker(store, K, S, transport=t).submit(oid, now) == "broker-123"
    m, url, body = calls[0]
    assert m == "POST" and url == "https://paper-api.alpaca.markets/v2/orders"
    assert body["client_order_id"] == oid and body["symbol"] == "AAPL" and body["time_in_force"] == "day"


def test_only_paper_mode_sleeve_orders_and_approved_orders(setup):
    store, acct, now = setup
    b = AlpacaPaperBroker(store, K, S, transport=lambda *a: {"id": "x"})
    sim = propose_order(store, req(acct), now)
    with pytest.raises(NexusError, match="paper_broker"):
        b.submit(sim, now)
    rejected = propose_order(store, req(acct, mode="paper_broker", quantity="100000"), now)
    with pytest.raises(NexusError, match="risk-approved"):
        b.submit(rejected, now)
    shadow = store.create_account(LedgerKind.SHADOW, "sh").account_id
    with pytest.raises(NexusError):
        propose_order(store, req(shadow, mode="paper_broker"), now)


def test_missing_broker_id_and_halt_fail_closed(setup):
    store, acct, now = setup
    oid = propose_order(store, req(acct, mode="paper_broker"), now)
    with pytest.raises(NexusError, match="no order id"):
        AlpacaPaperBroker(store, K, S, transport=lambda *a: {}).submit(oid, now)
    store.controls.halt("owner", "x")
    with pytest.raises(SystemHalted):
        AlpacaPaperBroker(store, K, S, transport=lambda *a: {"id": "x"}).submit(oid, now)


def test_internal_call_allowlist_and_live_host_unreachable(setup):
    store, _, _ = setup
    b = AlpacaPaperBroker(store, K, S, transport=lambda *a: {})
    for method, path in [("POST", "/v2/account/activities"), ("PUT", "/v2/orders"), ("POST", "/v1/transfers"),
                         ("DELETE", "/v2/positions"), ("POST", "/v2/account/ach")]:
        with pytest.raises(LaunchBoundaryViolation):
            b._call(method, path)
    with pytest.raises(LaunchBoundaryViolation):
        urllib_transport("POST", "https://api.alpaca.markets/v2/orders", {}, {})


def test_env_credentials_required(setup):
    store, _, _ = setup
    with pytest.raises(SecretError):
        AlpacaPaperBroker.from_env(store, {})
    b = AlpacaPaperBroker.from_env(store, {"NEXUS_ALPACA_PAPER_KEY_ID": "aaaaaa111", "NEXUS_ALPACA_PAPER_SECRET_KEY": "bbbbbb222"},
                                   transport=lambda *a: {})
    assert "aaaaaa" not in repr(b._k)


def test_no_live_capability_reachable_from_broker_module():
    import nexus.brokers.alpaca_paper as m
    src = open(m.__file__).read()
    assert "api.alpaca.markets/" not in src.replace("paper-api.alpaca.markets", "")
