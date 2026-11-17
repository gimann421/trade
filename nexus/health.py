"""Operational health: pure read-only report. Unhealthy means a human should look; it never changes state."""
from __future__ import annotations

import json
from datetime import datetime, timedelta

from .errors import NexusError
from .scheduler import JobSpec, paused_jobs
from .store import Store
from .timeutil import from_iso, require_aware, to_iso


def report(store: Store, jobs: list[JobSpec], now: datetime) -> dict:
    now = require_aware(now, "now")
    out: dict = {"as_of": to_iso(now), "halted": store.controls.is_halted(), "paused_jobs": sorted(paused_jobs(store)), "problems": []}
    try:
        out["audit_events"] = store.events.verify_chain()
    except NexusError as exc:
        out["audit_events"] = None
        out["problems"].append(f"audit chain: {exc}")
    out["jobs"] = {}
    for j in jobs:
        last_ok = store.conn.execute("SELECT MAX(at) AS m FROM job_events WHERE job_name=? AND kind='succeeded'", (j.name,)).fetchone()["m"]
        missed = store.conn.execute("SELECT COUNT(*) FROM job_events WHERE job_name=? AND kind='missed' AND at>?",
                                    (j.name, to_iso(now - timedelta(days=1)))).fetchone()[0]
        last_kind = store.conn.execute("SELECT kind FROM job_events WHERE job_name=? ORDER BY seq DESC LIMIT 1", (j.name,)).fetchone()
        stale = last_ok is None or now - from_iso(last_ok) > 2 * j.every + j.grace
        out["jobs"][j.name] = {"last_success": last_ok, "missed_24h": missed, "last_event": last_kind[0] if last_kind else None, "stale": stale}
        if stale and j.name not in out["paused_jobs"]:
            out["problems"].append(f"job {j.name} has no recent success")
        if missed:
            out["problems"].append(f"job {j.name} missed {missed} run(s) in 24h")
    if out["halted"]:
        out["problems"].append("emergency stop is active")
    out["healthy"] = not out["problems"]
    return out
