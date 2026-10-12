import sqlite3

import pytest

from core import broker
from core.broker import LiveAccountError, get_paper_client
from core.config import ConfigError, PaperKeys, load_paper_keys
from core.ledger import add_evidence, add_hypothesis, connect, set_status
from core.risk import load_risk_limits

FAKE = PaperKeys("fake-key-id", "fake-secret")


def test_keys_never_in_repr(tmp_path):
    env = tmp_path / ".env"
    env.write_text("ALPACA_PAPER_API_KEY=abc123\nALPACA_PAPER_SECRET_KEY=shh456\n")
    keys = load_paper_keys(env)
    assert keys.api_key == "abc123"
    for text in (repr(keys), str(keys), f"{keys}"):
        assert "abc123" not in text and "shh456" not in text


def test_missing_keys_raise(tmp_path):
    env = tmp_path / ".env"
    env.write_text("ALPACA_PAPER_API_KEY=\nALPACA_PAPER_SECRET_KEY=\n")
    with pytest.raises(ConfigError, match="ALPACA_PAPER_API_KEY"):
        load_paper_keys(env)


def test_client_uses_paper_endpoint():
    client = get_paper_client(FAKE, verify_account=False)
    assert "paper-api" in str(client._base_url.value)


def test_live_endpoint_refused(monkeypatch):
    real = broker.TradingClient
    monkeypatch.setattr(broker, "TradingClient",
                        lambda k, s, paper: real(k, s, paper=False))
    with pytest.raises(LiveAccountError):
        get_paper_client(FAKE, verify_account=False)


def test_live_account_number_refused(monkeypatch):
    class Account:
        account_number = "123456789"
    monkeypatch.setattr(broker.TradingClient, "get_account", lambda self: Account())
    with pytest.raises(LiveAccountError):
        get_paper_client(FAKE)


def test_risk_limits_load():
    limits = load_risk_limits()
    assert 0 < limits.max_position_pct <= 100


def test_ledger_roundtrip(tmp_path):
    conn = connect(tmp_path / "ledger.db")
    hid = add_hypothesis(conn, "t", "SPY drifts up after 3 down days")
    add_evidence(conn, hid, "backtest", "Sharpe 0.4 over 2010-2024", "inconclusive")
    set_status(conn, hid, "testing")
    assert conn.execute("SELECT status FROM hypotheses").fetchone()[0] == "testing"
    with pytest.raises(sqlite3.IntegrityError):
        set_status(conn, hid, "bogus")
