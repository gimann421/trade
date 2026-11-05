"""Ingestion: fetch -> quality-check -> persist with lineage, as one retry-safe unit.

Point-in-time rule: a bar is only visible to consumers from ``ingested_at`` onward, and a snapshot
is never rewritten; a corrected fetch becomes a new snapshot.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from . import permissions
from .adapters.base import MarketDataAdapter
from .calendars import get_calendar
from .domain.enums import DataQuality, EventType
from .domain.models import Bar, DataSnapshot, content_hash
from .errors import NexusError, StaleOrInvalidDataError
from .quality import QualityReport, check_bars, check_fresh
from .store import Store
from .timeutil import require_aware, to_iso

CALENDAR_BY_ASSET = {"digital_asset": "24x7"}


def calendar_for(store: Store, instrument_id: str):
    inst = store.get_instrument(instrument_id)
    if inst is None:
        raise NexusError(f"unregistered instrument {instrument_id}")
    return get_calendar(CALENDAR_BY_ASSET.get(inst.asset_class.value, "XNYS"))


def ingest_daily_bars(store: Store, adapter: MarketDataAdapter, instrument_id: str, start: date, end: date,
                      actor: str = "ingestion") -> tuple[DataSnapshot, QualityReport]:
    permissions.require(permissions.Capability.RESEARCH, store.config.permissions.allowed)
    cal = calendar_for(store, instrument_id)
    res = adapter.fetch_daily_bars(instrument_id, start, end)
    require_aware(res.as_of); require_aware(res.fetched_at)
    bars = sorted(res.bars, key=lambda b: b.session_date)
    report = check_bars(bars, cal, start, end)
    digest = content_hash([vars(b) for b in bars])
    snap_id = f"{res.source}:{instrument_id}:{digest[:16]}"
    existing = store.conn.execute("SELECT 1 FROM data_snapshots WHERE snapshot_id=?", (snap_id,)).fetchone()
    if existing:  # identical content already stored: idempotent retry
        return _load_snapshot(store, snap_id), report
    snap = DataSnapshot(snap_id, res.source, res.as_of, res.fetched_at, digest, report.quality, res.license_note)
    store.conn.execute("BEGIN IMMEDIATE")
    try:
        store.conn.execute("INSERT INTO data_snapshots VALUES (?,?,?,?,?,?,?)",
                           (snap.snapshot_id, snap.source, to_iso(snap.as_of), to_iso(snap.ingested_at),
                            snap.content_sha256, snap.quality.value, snap.license_note))
        store.conn.executemany("INSERT INTO bars VALUES (?,?,?,?,?,?,?,?)",
                               [(snap_id, b.instrument_id, b.session_date, b.open, b.high, b.low, b.close, b.volume)
                                for b in bars])
        store.conn.execute("COMMIT")
    except Exception:
        if store.conn.in_transaction:
            store.conn.execute("ROLLBACK")
        raise
    store.events.append(EventType.DATA_SNAPSHOT_RECORDED, res.source, actor,
                        {"snapshot_id": snap_id, "instrument_id": instrument_id, "quality": snap.quality.value,
                         "bars": len(bars), "sha256": digest}, idempotency_key=f"snap:{snap_id}")
    if not report.ok:
        store.events.append(EventType.DATA_QUALITY_FAILED, res.source, actor,
                            {"snapshot_id": snap_id, "quality": report.quality.value, "issues": report.issues[:20]},
                            idempotency_key=f"dq:{snap_id}")
    return snap, report


def _load_snapshot(store: Store, snapshot_id: str) -> DataSnapshot:
    from .timeutil import from_iso
    r = store.conn.execute("SELECT * FROM data_snapshots WHERE snapshot_id=?", (snapshot_id,)).fetchone()
    return DataSnapshot(r["snapshot_id"], r["source"], from_iso(r["as_of"]), from_iso(r["ingested_at"]),
                        r["content_sha256"], DataQuality(r["quality"]), r["license_note"])


def get_snapshot_bars(store: Store, snapshot_id: str) -> list[Bar]:
    """Exact, reproducible reload of one snapshot."""
    return [Bar(r["instrument_id"], r["session_date"], r["open"], r["high"], r["low"], r["close"], r["volume"])
            for r in store.conn.execute("SELECT * FROM bars WHERE snapshot_id=? ORDER BY instrument_id, session_date",
                                        (snapshot_id,))]


def verify_snapshot(store: Store, snapshot_id: str) -> None:
    snap = _load_snapshot(store, snapshot_id)
    if content_hash([vars(b) for b in get_snapshot_bars(store, snapshot_id)]) != snap.content_sha256:
        raise StaleOrInvalidDataError(f"snapshot {snapshot_id} content no longer matches its hash")


def bars_known_at(store: Store, instrument_id: str, as_known_at: datetime) -> list[Bar]:
    """Point-in-time view: only OK snapshots ingested at or before ``as_known_at``; the latest
    snapshot wins per session date (a later snapshot never leaks into an earlier view)."""
    rows = store.conn.execute(
        "SELECT b.*, s.ingested_at FROM bars b JOIN data_snapshots s USING (snapshot_id) "
        "WHERE b.instrument_id=? AND s.quality='ok' AND s.ingested_at<=? ORDER BY b.session_date, s.ingested_at",
        (instrument_id, to_iso(as_known_at))).fetchall()
    latest = {r["session_date"]: r for r in rows}
    return [Bar(r["instrument_id"], r["session_date"], r["open"], r["high"], r["low"], r["close"], r["volume"])
            for _, r in sorted(latest.items())]


class DecisionDataGate:
    """Every decision must pass this first. Fails closed: unknown instrument, no OK data, or stale data blocks."""

    def __init__(self, store: Store):
        self.store = store

    def grace(self) -> timedelta:
        minutes = self.store.config.risk_limits.get("data_quality", {}).get("daily_bar_grace_minutes_after_close")
        if not isinstance(minutes, (int, float)) or isinstance(minutes, bool) or minutes < 0:
            raise StaleOrInvalidDataError("daily_bar_grace_minutes_after_close not configured; cannot judge freshness")
        return timedelta(minutes=minutes)

    def check(self, instrument_id: str, now: datetime) -> QualityReport:
        cal = calendar_for(self.store, instrument_id)
        bars = bars_known_at(self.store, instrument_id, now)
        rep = check_fresh(bars[-1].session_date if bars else None, cal, now, self.grace())
        if not rep.ok:
            self.store.events.append(EventType.DATA_QUALITY_FAILED, "decision_gate", "system",
                                    {"instrument_id": instrument_id, "quality": rep.quality.value, "issues": rep.issues})
        return rep

    def require(self, instrument_id: str, now: datetime) -> None:
        self.store.controls.assert_can_create_simulated_orders()
        self.check(instrument_id, now).require_ok()
