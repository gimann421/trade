import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from nexus.db.migrate import connect, migrate
from nexus.domain import (AssetClass, CapabilityTier, DataQuality, DataSnapshot, Instrument, LedgerKind,
                          OrderState, ALLOWED_ORDER_TRANSITIONS)
from nexus.errors import NexusError, StaleOrInvalidDataError


def inst(**kw):
    base = dict(instrument_id="EQ:XNAS:AAPL", symbols={"vendor": "AAPL"}, asset_class=AssetClass.EQUITY,
                currency="USD", timezone="America/New_York", exchange="XNAS")
    base.update(kw)
    return Instrument(**base)


def test_migrations_apply_once_and_are_idempotent():
    c = connect(":memory:")
    assert migrate(c) == [1, 2]
    assert migrate(c) == []


def test_modified_applied_migration_is_detected(tmp_path):
    d = tmp_path / "m"
    d.mkdir()
    (d / "001_a.sql").write_text("CREATE TABLE t (x INTEGER);")
    c = connect(":memory:")
    migrate(c, d)
    (d / "001_a.sql").write_text("CREATE TABLE t (x INTEGER, y INTEGER);")
    with pytest.raises(NexusError, match="modified"):
        migrate(c, d)


def test_failed_migration_rolls_back(tmp_path):
    d = tmp_path / "m"
    d.mkdir()
    (d / "001_bad.sql").write_text("CREATE TABLE a (x INTEGER);\nINSERT INTO nope VALUES (1);")
    c = connect(":memory:")
    with pytest.raises(sqlite3.DatabaseError):
        migrate(c, d)
    assert c.execute("SELECT name FROM sqlite_master WHERE name='a'").fetchone() is None


def test_instrument_validation():
    for bad in [dict(instrument_id="AAPL"), dict(symbols={}), dict(currency="usd"), dict(timezone="Mars/Base"),
                dict(contract_multiplier=0), dict(tick_size=-1)]:
        with pytest.raises(NexusError):
            inst(**bad)


def test_registry_versions_and_roundtrip(store):
    assert store.register_instrument(inst()) == 1
    assert store.register_instrument(inst(capability_tier=CapabilityTier.R2)) == 2
    assert store.get_instrument("EQ:XNAS:AAPL").capability_tier == CapabilityTier.R2
    assert store.get_instrument("EQ:XNAS:AAPL", 1).capability_tier == CapabilityTier.R0
    assert store.get_instrument("missing:x:y") is None


def test_registry_refuses_r4_and_db_enforces_it(store):
    with pytest.raises(NexusError):
        store.register_instrument(inst(capability_tier=CapabilityTier.R4))
    with pytest.raises(sqlite3.DatabaseError):  # bypassing the API still fails
        store.conn.execute("INSERT INTO instruments VALUES ('x:y:z',1,'equity','R4','{}','t')")


def test_registry_is_append_only(store):
    store.register_instrument(inst())
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        store.conn.execute("UPDATE instruments SET capability_tier='R3'")


def test_three_ledger_kinds_are_separate_and_immutable(store):
    a = store.create_account(LedgerKind.ACTUAL, "owner")
    s = store.create_account(LedgerKind.SHADOW, "owner-shadow")
    p = store.create_account(LedgerKind.PAPER_SLEEVE, "momentum")
    assert {x.kind for x in store.list_accounts()} == set(LedgerKind)
    assert [x.account_id for x in store.list_accounts(LedgerKind.SHADOW)] == [s.account_id]
    assert len({a.account_id, s.account_id, p.account_id}) == 3
    with pytest.raises(sqlite3.DatabaseError, match="immutable"):
        store.conn.execute("UPDATE ledger_accounts SET kind='ACTUAL' WHERE kind='SHADOW'")
    with pytest.raises(sqlite3.DatabaseError):
        store.conn.execute("INSERT INTO ledger_accounts VALUES ('z','LIVE','n','t')")


def test_snapshot_lineage_and_freshness(store, clock):
    snap = DataSnapshot("s1", "fixture", clock.now - timedelta(seconds=30), clock.now, "ab" * 32, DataQuality.OK)
    store.record_snapshot(snap)
    snap.assert_fresh(clock.now, 60)
    with pytest.raises(StaleOrInvalidDataError):
        snap.assert_fresh(clock.now + timedelta(minutes=5), 60)
    with pytest.raises(StaleOrInvalidDataError):
        snap.assert_fresh(clock.now, None)   # no limit configured -> cannot call data current


def test_snapshot_rejects_bad_inputs(clock):
    with pytest.raises(NexusError):
        DataSnapshot("s", "", clock.now, clock.now, "x")
    with pytest.raises(NexusError):
        DataSnapshot("s", "src", datetime(2026, 1, 1), clock.now, "x")
    with pytest.raises(StaleOrInvalidDataError):  # as-of after ingestion is contradictory
        DataSnapshot("s", "src", clock.now + timedelta(hours=1), clock.now, "x")
    unverified = DataSnapshot("s", "src", clock.now, clock.now, "x")
    with pytest.raises(StaleOrInvalidDataError):
        unverified.assert_fresh(clock.now, 60)


def test_order_state_machine_is_closed_and_terminal_states_are_final():
    assert set(ALLOWED_ORDER_TRANSITIONS) == set(OrderState)
    for terminal in (OrderState.SETTLED, OrderState.REJECTED, OrderState.CANCELED, OrderState.EXPIRED):
        assert not ALLOWED_ORDER_TRANSITIONS[terminal]
    assert OrderState.FILLED not in ALLOWED_ORDER_TRANSITIONS[OrderState.PROPOSED]  # cannot skip simulator acceptance
    for tos in ALLOWED_ORDER_TRANSITIONS.values():
        assert tos <= set(OrderState)
