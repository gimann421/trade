"""Deterministic job scheduler: idempotent, retry-safe, restart-safe, honest about missed runs.

A job has fixed time slots (anchor + k*interval). Each slot is run to success at most once. Slots that were never
started before ``grace`` elapsed are recorded as MISSED (and optionally the latest is caught up) so the history never
implies a check ran when it did not. The kill switch and per-job pauses are honoured on every attempt; the system
fails closed when the audit chain does not verify.
"""
from __future__ import annotations

import json
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable, Protocol

from .domain.enums import EventType
from .errors import NexusError
from .store import Store
from .timeutil import from_iso, require_aware, to_iso


@dataclass(frozen=True)
class JobSpec:
    name: str
    fn: Callable[[Store, datetime], dict | None]       # (store, scheduled_for) -> small JSON-able result
    every: timedelta
    anchor: datetime
    max_attempts: int = 3
    grace: timedelta = timedelta(minutes=30)
    catch_up_latest: bool = False                       # run the most recent missed slot once on restart

    def __post_init__(self):
        require_aware(self.anchor, "anchor")
        if self.every <= timedelta(0) or self.max_attempts < 1:
            raise NexusError("bad job spec")

    def slots_until(self, now: datetime, after: datetime | None) -> list[datetime]:
        if now < self.anchor:
            return []
        n = int((now - self.anchor) / self.every)
        slots = [self.anchor + k * self.every for k in range(max(0, n - 1000), n + 1)]   # bounded look-back
        return [s for s in slots if after is None or s > after]


class Notifier(Protocol):
    def notify(self, severity: str, message: str) -> None: ...


class LogNotifier:
    """Default notifier (channel unconfirmed): structured log line only."""
    def notify(self, severity: str, message: str) -> None:
        from .logs import get_logger
        get_logger("nexus.alerts").log(40 if severity == "error" else 30, message)


def _events(store: Store, job: str, slot: datetime):
    return store.conn.execute("SELECT * FROM job_events WHERE job_name=? AND scheduled_for=? ORDER BY seq",
                              (job, to_iso(slot))).fetchall()


def _add(store: Store, job: str, slot: datetime, attempt: int, kind: str, now: datetime, detail: dict | None = None) -> None:
    store.conn.execute("INSERT INTO job_events (job_name, scheduled_for, attempt, kind, at, detail_json) VALUES (?,?,?,?,?,?)",
                       (job, to_iso(slot), attempt, kind, to_iso(now), json.dumps(detail or {}, sort_keys=True)))


def paused_jobs(store: Store) -> set[str]:
    out: set[str] = set()
    for r in store.conn.execute("SELECT event_type, payload_json FROM events WHERE event_type IN (?,?) ORDER BY seq",
                                (EventType.CONTROL_PAUSE_JOB.value, EventType.CONTROL_RESUME_JOB.value)):
        name = json.loads(r["payload_json"])["job"]
        (out.add if r["event_type"] == EventType.CONTROL_PAUSE_JOB.value else out.discard)(name)
    return out


def pause_job(store: Store, name: str, actor: str, reason: str) -> None:
    store.events.append(EventType.CONTROL_PAUSE_JOB, "controls", actor, {"job": name, "reason": reason})


def resume_job(store: Store, name: str, actor: str, reason: str) -> None:
    store.events.append(EventType.CONTROL_RESUME_JOB, "controls", actor, {"job": name, "reason": reason})


class Scheduler:
    def __init__(self, store: Store, jobs: list[JobSpec], notifier: Notifier | None = None):
        names = [j.name for j in jobs]
        if len(set(names)) != len(names):
            raise NexusError("duplicate job names")
        self.store, self.jobs, self.notifier = store, {j.name: j for j in jobs}, notifier or LogNotifier()

    def tick(self, now: datetime) -> dict[str, list[str]]:
        """Process every job once. Returns {job: [outcomes]} for visibility and tests."""
        now = require_aware(now, "now")
        report: dict[str, list[str]] = {}
        try:
            self.store.events.verify_chain()
            chain_ok = True
        except NexusError as exc:
            chain_ok = False
            self.notifier.notify("error", f"audit chain failed verification; no jobs will run: {exc}")
        halted = self.store.controls.is_halted()
        paused = paused_jobs(self.store)
        for name, job in self.jobs.items():
            report[name] = []
            last = self.store.conn.execute("SELECT MAX(scheduled_for) AS m FROM job_events WHERE job_name=?", (name,)).fetchone()["m"]
            slots = job.slots_until(now, from_iso(last) if last else None)
            # also revisit the latest slot with a failed attempt for retry
            retry = self.store.conn.execute(
                "SELECT scheduled_for FROM job_events WHERE job_name=? GROUP BY scheduled_for ORDER BY scheduled_for DESC LIMIT 1", (name,)).fetchone()
            if retry and from_iso(retry["scheduled_for"]) not in slots:
                slots = [from_iso(retry["scheduled_for"])] + slots
            for i, slot in enumerate(slots):
                evs = _events(self.store, name, slot)
                kinds = [e["kind"] for e in evs]
                if "succeeded" in kinds or "missed" in kinds:
                    continue
                attempts = sum(1 for k in kinds if k == "started")
                is_latest = i == len(slots) - 1
                stale = now - slot > job.grace
                if stale and attempts == 0 and not (job.catch_up_latest and is_latest):
                    _add(self.store, name, slot, 0, "missed", now, {"reason": "not started within grace"})
                    self.notifier.notify("warn", f"job {name} missed slot {to_iso(slot)}")
                    report[name].append(f"missed:{to_iso(slot)}")
                    continue
                if attempts >= job.max_attempts:
                    continue
                if not chain_ok or halted or name in paused:
                    kind = "skipped_paused" if name in paused else "skipped_halted"
                    if not kinds or kinds[-1] != kind:
                        _add(self.store, name, slot, attempts, kind, now, {"chain_ok": chain_ok})
                    report[name].append(f"{kind}:{to_iso(slot)}")
                    continue
                report[name].append(self._run(job, slot, attempts + 1, now))
        return report

    def _run(self, job: JobSpec, slot: datetime, attempt: int, now: datetime) -> str:
        _add(self.store, job.name, slot, attempt, "started", now)
        try:
            result = job.fn(self.store, slot) or {}
            _add(self.store, job.name, slot, attempt, "succeeded", now, {"result": result})
            return f"succeeded:{to_iso(slot)}"
        except Exception as exc:  # a failing job never kills the loop; it is recorded and retried
            _add(self.store, job.name, slot, attempt, "failed", now, {"error": f"{type(exc).__name__}: {str(exc)[:300]}"})
            self.notifier.notify("error", f"job {job.name} attempt {attempt} failed: {type(exc).__name__}")
            return f"failed:{to_iso(slot)}"

    def interrupted(self) -> list[tuple[str, str]]:
        """Jobs whose last event is 'started' (process died mid-run). They are retried on the next tick."""
        out = []
        for r in self.store.conn.execute("SELECT job_name, scheduled_for FROM job_events GROUP BY job_name, scheduled_for"):
            last = self.store.conn.execute("SELECT kind FROM job_events WHERE job_name=? AND scheduled_for=? ORDER BY seq DESC LIMIT 1",
                                           (r["job_name"], r["scheduled_for"])).fetchone()["kind"]
            if last == "started":
                out.append((r["job_name"], r["scheduled_for"]))
        return out
