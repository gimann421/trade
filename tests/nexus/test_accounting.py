import sqlite3
from datetime import timedelta
from decimal import Decimal

import pytest

from nexus.accounting import (D, create_shadow_from_snapshot, import_actual_snapshot, load_snapshot, log_shadow_path_decision,
                              nav, reconcile, record_entry, state_from_entries, actual_state, verify_cash_identity)
from nexus.domain import AssetClass, Instrument, LedgerKind
from nexus.errors import NexusError, StaleOrInvalidDataError

A, B = "EQ:XNAS:AAPL", "EQ:XNAS:MSFT"


@pytest.fixture
def s(store):
    for iid in (A, B):
        store.register_instrument(Instrument(iid, {"v": iid[-4:]}, AssetClass.EQUITY, "USD", "America/New_York"))
    return store


def snap(s, clock, **kw):
    acct = kw.pop("acct", None) or s.create_account(LedgerKind.ACTUAL, "owner").account_id
    sid = import_actual_snapshot(s, acct, clock.now, "statement", "Garret", cash={"USD": "1000.50"},
                                 holdings={A: {"quantity": "10", "cost_basis": "1500"}, B: {"quantity": "2.5"}},
                                 estimated_fields=["B.cost_basis"], **kw)
    return acct, sid


def test_floats_rejected():
    with pytest.raises(NexusError):
        D(0.1)


def test_trade_arithmetic_is_exact_and_validated(s, clock):
    p = s.create_account(LedgerKind.PAPER_SLEEVE, "mom").account_id
    record_entry(s, p, "DEPOSIT", clock.now, cash_delta="10000")
    record_entry(s, p, "TRADE", clock.now, instrument_id=A, qty_delta="10", price="187.33", fee="0.10", cash_delta="-1873.40")
    st = state_from_entries(s, p)
    assert st.cash == Decimal("8126.60") and st.positions == {A: Decimal(10)}
    with pytest.raises(NexusError, match="exactly"):
        record_entry(s, p, "TRADE", clock.now, instrument_id=A, qty_delta="1", price="100", cash_delta="-99.99")
    record_entry(s, p, "TRADE", clock.now, instrument_id=A, qty_delta="-4", price="190", cash_delta="760")
    assert state_from_entries(s, p).positions == {A: Decimal(6)}
    verify_cash_identity(s, p)


def test_sim_accounts_forbid_leverage_shorts_withdrawals(s, clock):
    p = s.create_account(LedgerKind.PAPER_SLEEVE, "x").account_id
    record_entry(s, p, "DEPOSIT", clock.now, cash_delta="100")
    with pytest.raises(NexusError, match="negative"):
        record_entry(s, p, "TRADE", clock.now, instrument_id=A, qty_delta="2", price="100", cash_delta="-200")
    with pytest.raises(NexusError, match="short"):
        record_entry(s, p, "TRADE", clock.now, instrument_id=A, qty_delta="-1", price="10", cash_delta="10")
    with pytest.raises(NexusError):
        record_entry(s, p, "WITHDRAWAL", clock.now, cash_delta="-5")


def test_unregistered_instrument_and_bad_kinds(s, clock):
    p = s.create_account(LedgerKind.PAPER_SLEEVE, "x").account_id
    record_entry(s, p, "DEPOSIT", clock.now, cash_delta="100")
    with pytest.raises(NexusError):
        record_entry(s, p, "TRADE", clock.now, instrument_id="EQ:X:NOPE", qty_delta="1", price="1", cash_delta="-1")
    with pytest.raises(NexusError):
        record_entry(s, p, "DEPOSIT", clock.now, cash_delta="-5")


def test_db_blocks_cross_ledger_entries(s, clock):
    actual, _ = snap(s, clock)
    shadow = s.create_account(LedgerKind.SHADOW, "sh").account_id
    ins = "INSERT INTO ledger_entries (entry_id, account_id, occurred_at, recorded_at, kind, origin, qty_delta, cash_delta) VALUES (?,?,?,?,?,?,?,?)"
    with pytest.raises(sqlite3.DatabaseError, match="ACTUAL"):
        s.conn.execute(ins, ("e1", actual, "t", "t", "DEPOSIT", "simulated", "0", "1"))
    with pytest.raises(sqlite3.DatabaseError, match="ACTUAL"):
        s.conn.execute(ins, ("e2", shadow, "t", "t", "DEPOSIT", "owner_confirmed", "0", "1"))
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        record_entry(s, shadow, "DEPOSIT", clock.now, cash_delta="5")
        s.conn.execute("UPDATE ledger_entries SET cash_delta='9'")


def test_actual_snapshot_requires_confirmation_and_account_kind(s, clock):
    shadow = s.create_account(LedgerKind.SHADOW, "sh").account_id
    with pytest.raises(NexusError, match="ACTUAL"):
        import_actual_snapshot(s, shadow, clock.now, "x", "Garret", cash={"USD": "1"}, holdings={})
    actual = s.create_account(LedgerKind.ACTUAL, "owner").account_id
    with pytest.raises(NexusError, match="confirmed"):
        import_actual_snapshot(s, actual, clock.now, "x", "", cash={"USD": "1"}, holdings={})
    with pytest.raises(StaleOrInvalidDataError, match="unverified"):
        actual_state(s, actual)


def test_snapshots_immutable_and_history_kept(s, clock):
    actual, sid1 = snap(s, clock)
    clock.advance(days=1)
    sid2 = import_actual_snapshot(s, actual, clock.now, "statement2", "Garret", cash={"USD": "5"}, holdings={A: {"quantity": "1"}})
    assert sid1 != sid2 and load_snapshot(s, sid1)["cash"] == {"USD": "1000.50"}
    assert actual_state(s, actual).positions == {A: Decimal(1)}
    assert s.conn.execute("SELECT supersedes FROM portfolio_snapshots WHERE snapshot_id=?", (sid2,)).fetchone()[0] == sid1
    with pytest.raises(sqlite3.DatabaseError, match="immutable"):
        s.conn.execute("UPDATE portfolio_snapshots SET source='x'")
    assert load_snapshot(s, sid1)["estimated_fields"] == ["B.cost_basis"]


def test_snapshot_tamper_detected(s, clock):
    _, sid = snap(s, clock)
    s.conn.execute("DROP TRIGGER portfolio_snapshots_no_update")
    s.conn.execute("UPDATE portfolio_snapshots SET holdings_json='{}'")
    with pytest.raises(StaleOrInvalidDataError):
        load_snapshot(s, sid)


def test_shadow_copies_actual_without_touching_it(s, clock):
    actual, sid = snap(s, clock)
    before = actual_state(s, actual)
    n_actual_entries = s.conn.execute("SELECT COUNT(*) FROM ledger_entries WHERE account_id=?", (actual,)).fetchone()[0]
    sh = create_shadow_from_snapshot(s, sid, "shadow", clock.now)
    st = state_from_entries(s, sh)
    assert st.cash == before.cash and st.positions == before.positions
    record_entry(s, sh, "TRADE", clock.now, instrument_id=A, qty_delta="-5", price="200", cash_delta="1000")   # shadow trades
    assert actual_state(s, actual) == before
    assert s.conn.execute("SELECT COUNT(*) FROM ledger_entries WHERE account_id=?", (actual,)).fetchone()[0] == n_actual_entries
    assert state_from_entries(s, sh).positions[A] == Decimal(5)


def test_shadow_path_decision_logged_and_validated(s, clock):
    actual, sid = snap(s, clock)
    sh = create_shadow_from_snapshot(s, sid, "shadow", clock.now)
    with pytest.raises(NexusError):
        log_shadow_path_decision(s, sh, sid, "overwrite", "x")
    with pytest.raises(NexusError):
        log_shadow_path_decision(s, sh, sid, "reset", "")
    log_shadow_path_decision(s, sh, sid, "maintain_parallel", "owner added cash")
    assert [e for e in s.events.all() if e.event_type.value == "shadow.path_decision"][0].payload["choice"] == "maintain_parallel"


def test_nav_fails_closed_without_marks_and_reconciles(s, clock):
    actual, _ = snap(s, clock)
    st = actual_state(s, actual)
    assert nav(st, {A: Decimal(200), B: Decimal(400)}) == Decimal("1000.50") + 2000 + 1000
    for bad in ({A: Decimal(200)}, {A: Decimal(200), B: Decimal(0)}):
        with pytest.raises(StaleOrInvalidDataError):
            nav(st, bad)
    assert reconcile(st, "1000.50", {A: "10", B: "2.5"}).ok
    rep = reconcile(st, "900", {A: "9"})
    assert not rep.ok and len(rep.diffs) == 3
    assert reconcile(st, "1000.505", {A: "10", B: "2.5"}).ok          # within 1 cent tolerance


def test_as_of_filters_entries(s, clock):
    p = s.create_account(LedgerKind.PAPER_SLEEVE, "x").account_id
    record_entry(s, p, "DEPOSIT", clock.now, cash_delta="100")
    record_entry(s, p, "DEPOSIT", clock.now + timedelta(days=1), cash_delta="50")
    assert state_from_entries(s, p, clock.now).cash == 100 and state_from_entries(s, p).cash == 150
