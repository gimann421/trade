import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from nexus.domain.enums import EventType
from nexus.errors import AuditChainError, NexusError, SystemHalted


def test_append_chains_and_verifies(store):
    e1 = store.events.append(EventType.SYSTEM_BOOT, "t", "a", {"n": 1})
    e2 = store.events.append(EventType.SYSTEM_BOOT, "t", "a", {"n": 2})
    assert e2.prev_hash == e1.hash and e1.prev_hash == "0" * 64
    assert store.events.verify_chain() == 2


def test_recorded_at_comes_from_system_clock_with_timezone(store, clock):
    e = store.events.append(EventType.SYSTEM_BOOT, "t", "a", {})
    assert e.recorded_at == clock.now and e.recorded_at.tzinfo is not None
    assert e.source == "t"


def test_naive_timestamp_rejected(store):
    with pytest.raises(NexusError):
        store.events.append(EventType.SYSTEM_BOOT, "t", "a", {}, occurred_at=datetime(2026, 1, 1))


def test_update_and_delete_blocked_by_database(store):
    store.events.append(EventType.SYSTEM_BOOT, "t", "a", {})
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        store.conn.execute("UPDATE events SET actor='evil'")
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        store.conn.execute("DELETE FROM events")


def test_tampering_detected_even_if_triggers_dropped(store):
    for i in range(3):
        store.events.append(EventType.SYSTEM_BOOT, "t", "a", {"n": i})
    store.conn.execute("DROP TRIGGER events_no_update")
    store.conn.execute("UPDATE events SET payload_json='{\"n\":99}' WHERE seq=2")
    with pytest.raises(AuditChainError):
        store.events.verify_chain()


def test_deleted_middle_event_detected(store):
    for i in range(3):
        store.events.append(EventType.SYSTEM_BOOT, "t", "a", {"n": i})
    store.conn.execute("DROP TRIGGER events_no_delete")
    store.conn.execute("DELETE FROM events WHERE seq=2")
    with pytest.raises(AuditChainError):
        store.events.verify_chain()


def test_idempotent_retry_returns_same_event(store):
    a = store.events.append(EventType.SYSTEM_BOOT, "t", "a", {"n": 1}, idempotency_key="job-1")
    b = store.events.append(EventType.SYSTEM_BOOT, "t", "a", {"n": 1}, idempotency_key="job-1")
    assert a.event_id == b.event_id and store.events.count() == 1


def test_idempotency_key_reuse_with_different_content_refused(store):
    store.events.append(EventType.SYSTEM_BOOT, "t", "a", {"n": 1}, idempotency_key="job-1")
    with pytest.raises(NexusError):
        store.events.append(EventType.SYSTEM_BOOT, "t", "a", {"n": 2}, idempotency_key="job-1")


def test_decision_events_cannot_be_backdated_or_future_dated(store, clock):
    ok = store.events.append(EventType.DECISION_RECORDED, "t", "a", {}, occurred_at=clock.now - timedelta(seconds=2))
    assert ok.seq == 1
    with pytest.raises(NexusError, match="backdating"):
        store.events.append(EventType.DECISION_RECORDED, "t", "a", {}, occurred_at=clock.now - timedelta(hours=1))
    with pytest.raises(NexusError, match="backdating"):
        store.events.append(EventType.DECISION_RECORDED, "t", "a", {}, occurred_at=clock.now + timedelta(minutes=5))
    with pytest.raises(NexusError, match="explicit occurred_at"):
        store.events.append(EventType.DECISION_RECORDED, "t", "a", {})


def test_non_decision_events_may_describe_the_past(store, clock):
    e = store.events.append(EventType.DATA_SNAPSHOT_RECORDED, "t", "a", {},
                            occurred_at=clock.now - timedelta(days=3))
    assert e.occurred_at < e.recorded_at


def test_corrections_append_and_reference_original(store):
    orig = store.events.append(EventType.SYSTEM_BOOT, "t", "a", {"n": 1})
    c = store.events.append_correction(orig.event_id, "typo", "a")
    assert c.payload["corrects"] == orig.event_id and store.events.count() == 2
    with pytest.raises(NexusError):
        store.events.append_correction("nope", "x", "a")


def test_halt_blocks_new_simulated_orders_and_resume_restores(store):
    store.controls.assert_can_create_simulated_orders()
    store.controls.halt("owner", "test")
    assert store.controls.is_halted()
    with pytest.raises(SystemHalted):
        store.controls.assert_can_create_simulated_orders()
    store.controls.resume("owner", "ok")
    store.controls.assert_can_create_simulated_orders()


def test_broken_chain_blocks_new_simulated_orders(store):
    store.events.append(EventType.SYSTEM_BOOT, "t", "a", {})
    store.conn.execute("DROP TRIGGER events_no_update")
    store.conn.execute("UPDATE events SET actor='x'")
    with pytest.raises(AuditChainError):
        store.controls.assert_can_create_simulated_orders()


def test_halt_state_survives_restart(tmp_path, clock):
    from nexus.config import load_config
    from nexus.store import Store
    db = tmp_path / "n.sqlite3"
    s1 = Store(db, load_config(), clock=clock)
    s1.controls.halt("owner", "pause")
    s2 = Store(db, load_config(), clock=clock)
    assert s2.controls.is_halted()
