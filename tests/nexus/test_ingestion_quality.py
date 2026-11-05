from datetime import date, datetime, timedelta, timezone

import pytest

from nexus.adapters.fixture import FixtureAdapter
from nexus.calendars import NyseCalendar
from nexus.domain import AssetClass, Bar, DataQuality, Instrument
from nexus.errors import StaleOrInvalidDataError, SystemHalted
from nexus.ingestion import (DecisionDataGate, bars_known_at, get_snapshot_bars, ingest_daily_bars, verify_snapshot)
from nexus.quality import check_bars, check_fresh, check_sources_agree

IID = "EQ:XNAS:AAPL"
cal = NyseCalendar()
SESSIONS = cal.sessions_between(date(2026, 11, 2), date(2026, 11, 6))   # Mon-Fri, all open


def bar(d, close=100.0, **kw):
    v = dict(open=close, high=close + 1, low=close - 1, close=close, volume=1000.0)
    v.update(kw)
    return Bar(IID, d.isoformat(), **v)


def good(): return [bar(d, 100 + i) for i, d in enumerate(SESSIONS)]


@pytest.fixture
def s(store):
    store.register_instrument(Instrument(IID, {"fixture": "AAPL"}, AssetClass.EQUITY, "USD", "America/New_York"))
    return store


def test_clean_ingest_ok_and_reproducible(s, clock):
    snap, rep = ingest_daily_bars(s, FixtureAdapter(good(), clock=clock), IID, SESSIONS[0], SESSIONS[-1])
    assert rep.ok and snap.quality is DataQuality.OK and snap.as_of.tzinfo and snap.source == "fixture"
    assert get_snapshot_bars(s, snap.snapshot_id) == good()
    verify_snapshot(s, snap.snapshot_id)
    s.events.verify_chain()


def test_ingest_is_idempotent(s, clock):
    a = FixtureAdapter(good(), clock=clock)
    snap1, _ = ingest_daily_bars(s, a, IID, SESSIONS[0], SESSIONS[-1])
    snap2, _ = ingest_daily_bars(s, a, IID, SESSIONS[0], SESSIONS[-1])
    assert snap1.snapshot_id == snap2.snapshot_id
    assert s.conn.execute("SELECT COUNT(*) FROM bars").fetchone()[0] == 5


def test_unregistered_instrument_refused(s, clock):
    with pytest.raises(Exception, match="unregistered"):
        ingest_daily_bars(s, FixtureAdapter([], clock=clock), "EQ:XNAS:NOPE", SESSIONS[0], SESSIONS[-1])


def test_bars_are_append_only_and_tamper_detected(s, clock):
    snap, _ = ingest_daily_bars(s, FixtureAdapter(good(), clock=clock), IID, SESSIONS[0], SESSIONS[-1])
    import sqlite3
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        s.conn.execute("UPDATE bars SET close=1")
    s.conn.execute("DROP TRIGGER bars_no_update")
    s.conn.execute("UPDATE bars SET close=1 WHERE session_date=?", (SESSIONS[0].isoformat(),))
    with pytest.raises(StaleOrInvalidDataError):
        verify_snapshot(s, snap.snapshot_id)


@pytest.mark.parametrize("mutate,expect", [
    (lambda b: b[:2] + b[3:], DataQuality.MISSING),
    (lambda b: b + [b[0]], DataQuality.CONFLICTING),
    (lambda b: [bar(SESSIONS[0], high=90.0, low=95.0)] + b[1:], DataQuality.CONFLICTING),
    (lambda b: [bar(SESSIONS[0], close=float("nan"))] + b[1:], DataQuality.CONFLICTING),
    (lambda b: [bar(SESSIONS[0], close=-5.0, open=-5.0, high=-4.0, low=-6.0)] + b[1:], DataQuality.CONFLICTING),
    (lambda b: b + [bar(date(2026, 11, 7))], DataQuality.CONFLICTING),   # Saturday bar
])
def test_bad_data_detected(mutate, expect):
    rep = check_bars(mutate(good()), cal, SESSIONS[0], date(2026, 11, 7))
    assert rep.quality is expect and not rep.ok
    with pytest.raises(StaleOrInvalidDataError):
        rep.require_ok()


def test_bad_snapshot_stored_but_never_visible_to_decisions(s, clock):
    broken = good()[:2] + good()[3:]
    snap, rep = ingest_daily_bars(s, FixtureAdapter(broken, clock=clock), IID, SESSIONS[0], SESSIONS[-1])
    assert snap.quality is DataQuality.MISSING
    assert bars_known_at(s, IID, clock.now + timedelta(days=1)) == []
    assert any(e.event_type.value == "data.quality_failed" for e in s.events.all())


def test_point_in_time_no_leakage_and_later_snapshot_wins(s, clock):
    t0 = clock.now
    ingest_daily_bars(s, FixtureAdapter(good(), clock=clock), IID, SESSIONS[0], SESSIONS[-1])
    clock.advance(hours=2)
    revised = good()
    revised[-1] = bar(SESSIONS[-1], 555.0)
    ingest_daily_bars(s, FixtureAdapter(revised, clock=clock), IID, SESSIONS[0], SESSIONS[-1])
    before = bars_known_at(s, IID, t0 + timedelta(hours=1))
    after = bars_known_at(s, IID, clock.now)
    assert before[-1].close == 104.0 and after[-1].close == 555.0
    assert bars_known_at(s, IID, t0 - timedelta(seconds=1)) == []


def test_sources_conflict_detected():
    other = good()
    other[1] = bar(SESSIONS[1], 150.0)
    assert not check_sources_agree(good(), other).ok
    assert check_sources_agree(good(), good()).ok


def test_freshness_rules():
    after_close = datetime(2026, 11, 6, 22, 30, tzinfo=timezone.utc)
    last = SESSIONS[-1].isoformat()
    assert check_fresh(last, cal, after_close, timedelta(hours=1)).ok
    assert check_fresh(SESSIONS[-2].isoformat(), cal, after_close, timedelta(hours=1)).quality is DataQuality.STALE
    # within grace of the close the previous session is still acceptable
    assert check_fresh(SESSIONS[-2].isoformat(), cal, datetime(2026, 11, 6, 21, 30, tzinfo=timezone.utc), timedelta(hours=1)).ok
    assert check_fresh(None, cal, after_close, timedelta(hours=1)).quality is DataQuality.MISSING


def test_gate_blocks_when_stale_missing_halted_or_unconfigured(s, clock):
    gate = DecisionDataGate(s)
    ingest_daily_bars(s, FixtureAdapter(good(), clock=clock), IID, SESSIONS[0], SESSIONS[-1])
    fresh_now = datetime(2026, 11, 6, 22, 30, tzinfo=timezone.utc)
    clock.now = fresh_now
    gate.require(IID, fresh_now)                                            # fresh: passes
    with pytest.raises(StaleOrInvalidDataError):
        gate.require(IID, fresh_now + timedelta(days=3))                    # Monday evening, no Monday bar
    from nexus.errors import NexusError
    with pytest.raises(NexusError):
        gate.require("EQ:XNAS:OTHER", fresh_now)                            # unknown instrument
    s.controls.halt("owner", "test")
    with pytest.raises(SystemHalted):
        gate.require(IID, fresh_now)


def test_gate_fails_closed_without_configured_grace(s, clock):
    s.config.risk_limits["data_quality"]["daily_bar_grace_minutes_after_close"] = None
    with pytest.raises(StaleOrInvalidDataError):
        DecisionDataGate(s).grace()


def test_fixture_csv_adapter(tmp_path, clock):
    p = tmp_path / "a.csv"
    p.write_text("date,open,high,low,close,volume\n2026-11-02,100,101,99,100.5,10\n")
    a = FixtureAdapter.from_csv(p, IID, clock=clock)
    r = a.fetch_daily_bars(IID, date(2026, 11, 1), date(2026, 11, 30))
    assert len(r.bars) == 1 and r.bars[0].close == 100.5 and r.fetched_at.tzinfo
