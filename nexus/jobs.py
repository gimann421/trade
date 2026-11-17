"""Concrete scheduled jobs. Adapters are injected; jobs never touch brokers or the real account."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Callable

from .accounting import load_snapshot
from .adapters.base import MarketDataAdapter
from .domain.enums import LedgerKind
from .errors import NexusError
from .ingestion import bars_known_at, ingest_daily_bars
from .recommendations import analyze, record_findings
from .scheduler import JobSpec
from .store import Store


def _registered_instruments(store: Store) -> list[str]:
    return [r[0] for r in store.conn.execute("SELECT DISTINCT instrument_id FROM instruments ORDER BY instrument_id")]


def heartbeat(store: Store, slot: datetime) -> dict:
    return {"events": store.events.count(), "halted": store.controls.is_halted()}


def audit_verify(store: Store, slot: datetime) -> dict:
    return {"events_verified": store.events.verify_chain()}


def make_ingest_job(adapter_factory: Callable[[], MarketDataAdapter], lookback_days: int = 40):
    """Ingest recent daily bars for every registered instrument. Per-instrument failures are collected; any failure fails the job
    (so it is retried and alerted) after all instruments were attempted."""
    def run(store: Store, slot: datetime) -> dict:
        adapter = adapter_factory()
        end = slot.date()
        start = end - timedelta(days=lookback_days)
        ok, bad = [], []
        for iid in _registered_instruments(store):
            try:
                _, rep = ingest_daily_bars(store, adapter, iid, start, end)
                (ok if rep.ok else bad).append(iid)
            except Exception as exc:
                bad.append(f"{iid}:{type(exc).__name__}")
        if bad:
            raise NexusError(f"ingestion problems for {len(bad)} instrument(s); {len(ok)} ok")
        return {"ingested": len(ok)}
    return run


def refresh_recommendations(store: Store, slot: datetime) -> dict:
    """Recompute advisory findings for the latest ACTUAL snapshot using the latest known bar closes. Advice only."""
    acct = store.conn.execute("SELECT account_id FROM ledger_accounts WHERE kind=? ORDER BY created_at DESC LIMIT 1", (LedgerKind.ACTUAL.value,)).fetchone()
    if acct is None:
        return {"skipped": "no actual account"}
    sid = store.conn.execute("SELECT snapshot_id FROM portfolio_snapshots WHERE account_id=? ORDER BY as_of DESC, rowid DESC LIMIT 1", (acct[0],)).fetchone()
    if sid is None:
        return {"skipped": "no confirmed snapshot"}
    snap = load_snapshot(store, sid[0])
    prices = {}
    for iid in snap["holdings"]:
        b = bars_known_at(store, iid, slot)
        if not b:
            raise NexusError(f"no OK bars for {iid}; cannot refresh recommendations")
        prices[iid] = Decimal(str(b[-1].close))
    new = record_findings(store, acct[0], sid[0], analyze(snap, prices, slot), slot)
    return {"new_recommendations": len(new)}


def default_jobs(adapter_factory: Callable[[], MarketDataAdapter] | None = None,
                 anchor: datetime = datetime(2026, 11, 17, 22, 30, tzinfo=timezone.utc)) -> list[JobSpec]:
    jobs = [JobSpec("heartbeat", heartbeat, timedelta(minutes=5), anchor, grace=timedelta(minutes=10)),
            JobSpec("audit_verify", audit_verify, timedelta(hours=1), anchor, grace=timedelta(hours=1))]
    if adapter_factory is not None:
        jobs.append(JobSpec("data_ingest", make_ingest_job(adapter_factory), timedelta(days=1), anchor,
                            max_attempts=6, grace=timedelta(hours=6), catch_up_latest=True))
        jobs.append(JobSpec("recommendations", refresh_recommendations, timedelta(days=1), anchor + timedelta(minutes=30),
                            max_attempts=3, grace=timedelta(hours=6), catch_up_latest=True))
    return jobs
