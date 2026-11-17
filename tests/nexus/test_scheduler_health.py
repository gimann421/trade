import json
from datetime import datetime, timedelta, timezone

import pytest

from nexus import cli
from nexus.health import report
from nexus.jobs import default_jobs, heartbeat
from nexus.scheduler import JobSpec, Scheduler, pause_job, paused_jobs, resume_job

T0 = datetime(2026, 11, 17, 22, 30, tzinfo=timezone.utc)


class Rec:
    def __init__(self): self.msgs = []
    def notify(self, sev, msg): self.msgs.append((sev, msg))


def job(fn, **kw):
    return JobSpec("j", fn, timedelta(hours=1), T0, **kw)


def kinds(store, name="j"):
    return [r["kind"] for r in store.conn.execute("SELECT kind FROM job_events WHERE job_name=? ORDER BY seq", (name,))]


def test_runs_each_slot_once_and_is_idempotent(store):
    calls = []
    s = Scheduler(store, [job(lambda st, slot: calls.append(slot) or {"n": len(calls)})], Rec())
    assert s.tick(T0 + timedelta(minutes=1))["j"] == [f"succeeded:{T0.isoformat(timespec='microseconds')}"]
    s.tick(T0 + timedelta(minutes=2))
    s.tick(T0 + timedelta(minutes=3))
    assert len(calls) == 1 and kinds(store) == ["started", "succeeded"]


def test_not_due_before_anchor(store):
    s = Scheduler(store, [job(lambda st, sl: None)], Rec())
    assert s.tick(T0 - timedelta(hours=1))["j"] == []


def test_retry_then_give_up_and_alert(store):
    n = {"c": 0}
    def flaky(st, slot):
        n["c"] += 1
        raise RuntimeError("boom")
    rec = Rec()
    s = Scheduler(store, [job(flaky, max_attempts=3)], rec)
    for i in range(6):
        s.tick(T0 + timedelta(minutes=i + 1))
    assert n["c"] == 3 and kinds(store).count("failed") == 3
    assert any(sev == "error" for sev, _ in rec.msgs)


def test_flaky_job_recovers_on_retry(store):
    n = {"c": 0}
    def flaky(st, slot):
        n["c"] += 1
        if n["c"] < 2:
            raise RuntimeError("once")
        return {"ok": 1}
    s = Scheduler(store, [job(flaky)], Rec())
    s.tick(T0 + timedelta(minutes=1)); s.tick(T0 + timedelta(minutes=2))
    assert kinds(store) == ["started", "failed", "started", "succeeded"]


def test_missed_slots_are_recorded_not_faked(store):
    calls = []
    rec = Rec()
    s = Scheduler(store, [job(lambda st, slot: calls.append(slot), grace=timedelta(minutes=10))], rec)
    s.tick(T0 + timedelta(hours=5, minutes=1))                 # system was down for 5 hours
    k = kinds(store)
    assert k.count("missed") == 5 and "succeeded" not in k[:5] and len(calls) == 1   # only the current slot ran
    assert any("missed slot" in m for _, m in rec.msgs)


def test_catch_up_latest_runs_one_missed_slot(store):
    calls = []
    s = Scheduler(store, [job(lambda st, slot: calls.append(slot), grace=timedelta(minutes=10), catch_up_latest=True)], Rec())
    s.tick(T0 + timedelta(hours=3, minutes=45))                # latest slot (T0+3h) is 45 min old: beyond grace but caught up
    assert len(calls) == 1 and calls[0] == T0 + timedelta(hours=3)


def test_halt_and_pause_block_runs_and_resume_works(store):
    calls = []
    s = Scheduler(store, [job(lambda st, slot: calls.append(1))], Rec())
    store.controls.halt("owner", "stop")
    out = s.tick(T0 + timedelta(minutes=1))
    assert out["j"][0].startswith("skipped_halted") and not calls
    store.controls.resume("owner", "go")
    s.tick(T0 + timedelta(minutes=2))
    assert len(calls) == 1
    pause_job(store, "j", "owner", "x")
    assert paused_jobs(store) == {"j"}
    s.tick(T0 + timedelta(hours=1, minutes=1))
    assert len(calls) == 1 and "skipped_paused" in kinds(store)
    resume_job(store, "j", "owner", "y")
    s.tick(T0 + timedelta(hours=1, minutes=2))
    assert len(calls) == 2


def test_broken_audit_chain_stops_all_jobs(store):
    calls = []
    s = Scheduler(store, [job(lambda st, slot: calls.append(1))], Rec())
    store.events.append(__import__("nexus.domain.enums", fromlist=["EventType"]).EventType.SYSTEM_BOOT, "t", "t", {})
    store.conn.execute("DROP TRIGGER events_no_update")
    store.conn.execute("UPDATE events SET actor='evil'")
    s.tick(T0 + timedelta(minutes=1))
    assert not calls


def test_survives_restart_and_detects_interrupted_run(tmp_path, clock):
    from nexus.config import load_config
    from nexus.store import Store
    db = tmp_path / "n.sqlite3"
    s1 = Store(db, load_config(), clock=clock)
    def crash(st, slot):
        raise KeyboardInterrupt        # simulates the process dying mid-job (not caught by the scheduler)
    with pytest.raises(KeyboardInterrupt):
        Scheduler(s1, [job(crash)], Rec()).tick(T0 + timedelta(minutes=1))
    s2 = Store(db, load_config(), clock=clock)
    sched2 = Scheduler(s2, [job(lambda st, slot: {"ok": 1})], Rec())
    assert sched2.interrupted() == [("j", T0.isoformat(timespec="microseconds"))]
    sched2.tick(T0 + timedelta(minutes=2))                       # retried after restart
    assert kinds(s2) == ["started", "started", "succeeded"] and sched2.interrupted() == []


def test_duplicate_job_names_rejected(store):
    with pytest.raises(Exception):
        Scheduler(store, [job(lambda s, t: None), job(lambda s, t: None)])


def test_health_reports_problems_honestly(store):
    jobs = [job(lambda st, sl: None)]
    rep = report(store, jobs, T0 + timedelta(hours=10))
    assert not rep["healthy"] and "job j has no recent success" in rep["problems"]
    Scheduler(store, jobs, Rec()).tick(T0 + timedelta(minutes=1))
    assert report(store, jobs, T0 + timedelta(minutes=2))["healthy"]
    store.controls.halt("o", "x")
    assert "emergency stop is active" in report(store, jobs, T0 + timedelta(minutes=3))["problems"]
    store.controls.resume("o", "y")
    Scheduler(store, jobs, Rec()).tick(T0 + timedelta(hours=10))       # long outage: skipped slots are reported
    assert any("missed" in p for p in report(store, jobs, T0 + timedelta(hours=10, minutes=1))["problems"])


def test_default_jobs_and_heartbeat(store):
    names = [j.name for j in default_jobs(None)]
    assert names == ["heartbeat", "audit_verify"]
    assert [j.name for j in default_jobs(lambda: None)][-2:] == ["data_ingest", "recommendations"]
    assert heartbeat(store, T0)["halted"] is False


def test_cli_tick_health_halt_resume(tmp_path, capsys, monkeypatch):
    for k in list(__import__("os").environ):
        if "ALPACA" in k:
            monkeypatch.delenv(k, raising=False)
    db = str(tmp_path / "n.sqlite3")
    assert cli.main(["boot", "--db", db]) == 0
    assert cli.main(["tick", "--db", db]) == 0
    assert cli.main(["halt", "--db", db]) == 0
    assert cli.main(["health", "--db", db]) == 1                   # halted => unhealthy
    assert cli.main(["resume", "--db", db]) == 0
