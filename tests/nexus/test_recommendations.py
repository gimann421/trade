import sqlite3
from datetime import timedelta
from decimal import Decimal

import pytest

from nexus.accounting import import_actual_snapshot, load_snapshot
from nexus.domain import AssetClass, Instrument, LedgerKind
from nexus.errors import NexusError, StaleOrInvalidDataError
from nexus.recommendations import add_note, analyze, record_findings

A, B, C = "EQ:US:AAA", "EQ:US:BBB", "EQ:US:CCC"
PRICES = {A: Decimal(100), B: Decimal(10), C: Decimal(50)}
THEMES = {"AAA": "chips", "BBB": "chips", "CCC": "other"}


@pytest.fixture
def env(store, clock):
    for i in (A, B, C):
        store.register_instrument(Instrument(i, {"v": i[-3:]}, AssetClass.EQUITY, "USD", "America/New_York"))
    acct = store.create_account(LedgerKind.ACTUAL, "real").account_id
    sid = import_actual_snapshot(store, acct, clock.now, "stmt", "Garret", cash={"USD": "1000"},
                                 holdings={A: {"quantity": "50", "cost_basis": "6000"},    # 5000 value, -1000 loss
                                           B: {"quantity": "50", "cost_basis": None},       # 500
                                           C: {"quantity": "20", "cost_basis": "900"}},     # 1000 value, +100 (1000 / 7500 = 13%: flagged)
                                 estimated_fields=["B.cost_basis"])
    return store, acct, sid


def kinds(fs): return {(f.kind, f.subject) for f in fs}


def test_findings(env, clock):
    store, acct, sid = env
    fs = analyze(load_snapshot(store, sid), PRICES, clock.now, themes=THEMES)
    k = kinds(fs)
    assert ("concentration_single", A) in k and ("concentration_single", B) not in k and ("concentration_single", C) in k
    assert ("concentration_theme", "chips") in k
    assert ("tax_loss_candidate", A) in k and ("tax_loss_candidate", C) not in k and ("tax_loss_candidate", B) not in k
    assert ("cash_share", "cash") in k and ("stale_snapshot", "portfolio") not in k
    tl = next(f for f in fs if f.kind == "tax_loss_candidate")
    assert "wash-sale" in tl.summary and "tax professional" in tl.summary and tl.evidence["unrealized"] == "-1000"


def test_stale_snapshot_and_missing_price(env, clock):
    store, acct, sid = env
    snap = load_snapshot(store, sid)
    assert ("stale_snapshot", "portfolio") in kinds(analyze(snap, PRICES, clock.now + timedelta(days=9)))
    with pytest.raises(StaleOrInvalidDataError):
        analyze(snap, {A: Decimal(100)}, clock.now)


def test_record_is_idempotent_preregistered_and_immutable(env, clock):
    store, acct, sid = env
    fs = analyze(load_snapshot(store, sid), PRICES, clock.now, themes=THEMES)
    ids = record_findings(store, acct, sid, fs, clock.now)
    assert len(ids) == len(fs)
    assert record_findings(store, acct, sid, fs, clock.now) == []                 # retry-safe
    ev = [e for e in store.events.all() if e.event_type.value == "recommendation.recorded"]
    assert len(ev) == len(fs) and all(e.occurred_at == clock.now for e in ev)
    with pytest.raises(sqlite3.DatabaseError, match="immutable"):
        store.conn.execute("UPDATE recommendations SET summary='x'")
    add_note(store, ids[0], "Garret", "owner_response", "will think about it", clock.now)
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        store.conn.execute("DELETE FROM recommendation_notes")


def test_only_actual_account_and_valid_snapshot(env, clock):
    store, acct, sid = env
    shadow = store.create_account(LedgerKind.SHADOW, "sh").account_id
    with pytest.raises(NexusError, match="ACTUAL"):
        record_findings(store, shadow, sid, [], clock.now)
    with pytest.raises(NexusError):
        add_note(store, "nope", "x", "outcome", "n", clock.now)


def test_recommendation_module_cannot_trade():
    import nexus.recommendations as m
    src = open(m.__file__).read()
    assert "orders" not in src.replace("ordinary", "") and "OrderRequest" not in src and "broker" not in src.lower()


def test_broad_funds_exempt_from_single_name_flag(env, clock):
    store, acct, sid = env
    fs = analyze(load_snapshot(store, sid), PRICES, clock.now, broad_funds=frozenset({"AAA"}))
    assert ("concentration_single", A) not in kinds(fs)
