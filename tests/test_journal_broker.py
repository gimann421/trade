from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from core import journal
from core.broker import RiskViolation, get_paper_client, submit_order
from core.config import PaperKeys
from core.risk import ProposedOrder, RiskLimits

LIMITS = RiskLimits(5.0, 50.0, 10, 5000, 2.0, False)
TODAY = datetime.now(timezone.utc).date().isoformat()


def fake_client(monkeypatch, positions=(), submit=None):
    client = get_paper_client(PaperKeys("fake", "fake"), verify_account=False)
    monkeypatch.setattr(client, "get_account",
                        lambda: SimpleNamespace(equity="100000", last_equity="100000"))
    monkeypatch.setattr(client, "get_all_positions",
                        lambda: [SimpleNamespace(symbol=s, market_value=str(v)) for s, v in positions])
    sent = []

    def _submit(request):
        sent.append(request)
        if submit:
            return submit(request)
        return SimpleNamespace(id="order-123")

    monkeypatch.setattr(client, "submit_order", _submit)
    return client, sent


def test_journal_requires_reasoning(tmp_path):
    with pytest.raises(ValueError):
        journal.record("hold", "  ", "x_v1.py", journal_dir=tmp_path)
    with pytest.raises(ValueError):
        journal.record("yolo", "because", "x_v1.py", journal_dir=tmp_path)


def test_journal_appends(tmp_path):
    journal.record("hold", "signal flat", "x_v1.py", journal_dir=tmp_path)
    journal.record("skip", "market closed", "x_v1.py", journal_dir=tmp_path)
    assert [e["action"] for e in journal.read(TODAY, tmp_path)] == ["hold", "skip"]


def test_submit_passes_and_journals(monkeypatch, tmp_path):
    client, sent = fake_client(monkeypatch)
    order = ProposedOrder("SPY", "buy", 5, 400)
    submit_order(client, order, "crossover fired", "sma_crossover_v1.py",
                 hypothesis_id=1, limits=LIMITS, journal_dir=tmp_path)
    assert len(sent) == 1 and sent[0].symbol == "SPY"
    [entry] = journal.read(TODAY, tmp_path)
    assert entry["action"] == "submitted" and entry["order_id"] == "order-123"
    assert entry["hypothesis_id"] == 1


def test_blocked_order_is_journaled_and_not_sent(monkeypatch, tmp_path):
    client, sent = fake_client(monkeypatch)
    with pytest.raises(RiskViolation):
        submit_order(client, ProposedOrder("SPY", "buy", 100, 400), "too big", "x_v1.py",
                     limits=LIMITS, journal_dir=tmp_path)
    assert sent == []
    [entry] = journal.read(TODAY, tmp_path)
    assert entry["action"] == "blocked" and entry["risk_violations"]


def test_broker_error_is_journaled(monkeypatch, tmp_path):
    def boom(request):
        raise ConnectionError("network down")
    client, _ = fake_client(monkeypatch, submit=boom)
    with pytest.raises(ConnectionError):
        submit_order(client, ProposedOrder("SPY", "buy", 1, 400), "test", "x_v1.py",
                     limits=LIMITS, journal_dir=tmp_path)
    [entry] = journal.read(TODAY, tmp_path)
    assert entry["action"] == "error" and "network down" in entry["extra"]["error"]


def test_submit_refuses_live_client(monkeypatch, tmp_path):
    from alpaca.trading.client import TradingClient
    from core.broker import LiveAccountError
    live = TradingClient("fake", "fake", paper=False)
    with pytest.raises(LiveAccountError):
        submit_order(live, ProposedOrder("SPY", "buy", 1, 400), "test", "x_v1.py",
                     limits=LIMITS, journal_dir=tmp_path)
    assert journal.read(TODAY, tmp_path) == []
