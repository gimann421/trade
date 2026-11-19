import json
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from nexus.adapters.fixture import FixtureAdapter
from nexus.domain.models import Bar
from nexus.errors import NexusError
from nexus.suggest import run, run_files

A, B = "EQ:US:AAA", "EQ:US:BBB"
TUE = datetime(2026, 11, 17, 21, 30, tzinfo=timezone.utc)
WED = datetime(2026, 11, 18, 21, 30, tzinfo=timezone.utc)
MON = datetime(2026, 11, 23, 21, 30, tzinfo=timezone.utc)
SNAP = {"as_of": "2026-11-17T15:00:00+00:00", "cash": {"USD": "1000"}, "estimated_fields": [],
        "holdings": {A: {"quantity": "50", "cost_basis": "6000"}, B: {"quantity": "50", "cost_basis": "400"}}}


def feed(a, b, day="2026-11-17"):
    return FixtureAdapter([Bar(A, day, a, a, a, a, 1), Bar(B, day, b, b, b, b, 1)])


def test_first_run_reports_then_quiet_then_change():
    r1 = run(SNAP, feed(100, 10), TUE, {})
    assert r1["post"] and any(l.startswith("NEW") for l in r1["lines"])
    r2 = run(SNAP, feed(100, 10), WED, r1["state"])
    assert not r2["post"] and r2["lines"] == []                     # nothing new -> silent
    r3 = run(SNAP, feed(60, 10), WED, r2["state"])                  # A drops: weight and loss move materially
    assert r3["post"] and any(l.startswith("CHANGED") for l in r3["lines"])


def test_cash_question_is_closed_so_no_monday_reminder():
    r1 = run(SNAP, feed(100, 10), TUE, {})
    mon = run(SNAP, feed(100, 10, "2026-11-20"), MON, r1["state"])
    assert not mon["post"]


def test_resolved_when_finding_goes_away():
    r1 = run(SNAP, feed(100, 10), TUE, {})
    r2 = run(SNAP, feed(100, 10), WED, {"posted": {**r1["state"]["posted"], "concentration_single:EQ:US:ZZZ": {"mag": "0.3"}}})
    assert any(l.startswith("RESOLVED") for l in r2["lines"])


def test_missing_price_fails_closed_but_labelled_fallback_works():
    ad = FixtureAdapter([Bar(A, "2026-11-17", 100, 100, 100, 100, 1)])
    with pytest.raises(NexusError):
        run(SNAP, ad, TUE, {})
    r = run(SNAP, ad, TUE, {}, fallback={B: Decimal(10)})
    assert B in r["price_notes"]


def test_stale_bar_is_not_used():
    with pytest.raises(NexusError):
        run(SNAP, feed(100, 10, day="2026-10-01"), TUE, {})


def test_files_roundtrip(tmp_path):
    sp, st = tmp_path / "snap.json", tmp_path / "state" / "s.json"
    sp.write_text(json.dumps(SNAP))
    r = run_files(str(sp), str(st), lambda: feed(100, 10), TUE)
    assert r["post"] and st.exists() and (tmp_path / "state" / "s.log.jsonl").exists()
    assert not run_files(str(sp), str(st), lambda: feed(100, 10), WED)["post"]
