from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from nexus.accounting import import_actual_snapshot, record_entry
from nexus.adapters.fixture import FixtureAdapter
from nexus.dashboard import render
from nexus.domain import AssetClass, Bar, CapabilityTier, Instrument, LedgerKind
from nexus.ingestion import ingest_daily_bars
from nexus.calendars import NyseCalendar

IID, XSS = "EQ:US:AAA", "EQ:US:EVIL"
cal = NyseCalendar()
SESS = cal.sessions_between(date(2026, 11, 2), date(2026, 11, 13))
NOW = datetime(2026, 11, 13, 23, 0, tzinfo=timezone.utc)


def test_dashboard_separates_ledgers_and_flags_unpriceable(store, clock):
    for i in (IID, XSS):
        store.register_instrument(Instrument(i, {"v": i[-3:]}, AssetClass.EQUITY, "USD", "America/New_York", capability_tier=CapabilityTier.R2))
    bars = [Bar(IID, d.isoformat(), 10, 11, 9, 10, 1e6) for d in SESS]
    ingest_daily_bars(store, FixtureAdapter(bars, clock=clock), IID, SESS[0], SESS[-1])
    actual = store.create_account(LedgerKind.ACTUAL, "real <b>x</b>").account_id
    import_actual_snapshot(store, actual, clock.now, "stmt", "Garret", cash={"USD": "100"},
                           holdings={IID: {"quantity": "10", "cost_basis": "90"}, XSS: {"quantity": "5", "cost_basis": None}})
    paper = store.create_account(LedgerKind.PAPER_SLEEVE, "sleeve").account_id
    record_entry(store, paper, "DEPOSIT", clock.now, cash_delta="5000")
    out = render(store, [], NOW)
    assert "ACTUAL: real &lt;b&gt;x&lt;/b&gt;" in out and "PAPER_SLEEVE: sleeve" in out       # escaped, separate sections
    assert "UNPRICEABLE" in out and "NAV is incomplete" in out and "cash identity OK" in out
    assert "advice only" in out and "Emergency stop: <b>off</b>" in out
    out2 = render(store, [], NOW, fallback_marks={XSS: Decimal("20")})
    assert "FALLBACK mark" in out2 and "UNPRICEABLE" not in out2


def test_dashboard_shows_halt(store, clock):
    store.controls.halt("owner", "x")
    assert "ACTIVE" in render(store, [], clock.now)
