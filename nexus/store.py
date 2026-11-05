"""Facade tying the DB, audit log, instrument registry, ledger accounts and data lineage together."""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Callable

from . import permissions
from .audit import EventStore
from .config import AppConfig, load_config
from .controls import Controls
from .db.migrate import connect, migrate
from .domain.enums import CapabilityTier, EventType, LedgerKind
from .domain.models import DataSnapshot, Instrument, LedgerAccount
from .errors import NexusError
from .timeutil import from_iso, to_iso, utcnow


class Store:
    def __init__(self, db_path: str | Path, config: AppConfig, clock: Callable[[], datetime] = utcnow):
        self.config = config
        self._clock = clock
        self.conn = connect(db_path)
        migrate(self.conn)
        self.events = EventStore(self.conn, clock, config.clock_skew_tolerance_seconds)
        self.controls = Controls(self.events)

    @classmethod
    def open(cls, db_path: str | Path | None = None, config: AppConfig | None = None, **kw) -> "Store":
        config = config or load_config()
        return cls(db_path or config.database_path, config, **kw)

    # ---- instrument registry (versioned, append-only) ----
    def register_instrument(self, inst: Instrument, actor: str = "system") -> int:
        permissions.require(permissions.Capability.RESEARCH, self.config.permissions.allowed)
        if inst.capability_tier.rank > self.config.permissions.max_tier.rank:
            raise NexusError(f"tier {inst.capability_tier.value} exceeds the permitted maximum "
                             f"{self.config.permissions.max_tier.value}")
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            v = self.conn.execute("SELECT COALESCE(MAX(version),0)+1 FROM instruments WHERE instrument_id=?",
                                  (inst.instrument_id,)).fetchone()[0]
            self.conn.execute("INSERT INTO instruments VALUES (?,?,?,?,?,?)",
                              (inst.instrument_id, v, inst.asset_class.value, inst.capability_tier.value,
                               json.dumps(inst.to_dict(), sort_keys=True), to_iso(self._clock())))
            self.conn.execute("COMMIT")
        except Exception:
            if self.conn.in_transaction:
                self.conn.execute("ROLLBACK")
            raise
        self.events.append(EventType.INSTRUMENT_REGISTERED, "instrument_registry", actor,
                           {"instrument_id": inst.instrument_id, "version": v, "tier": inst.capability_tier.value})
        return v

    def get_instrument(self, instrument_id: str, version: int | None = None) -> Instrument | None:
        q = "SELECT record_json FROM instruments WHERE instrument_id=? "
        row = (self.conn.execute(q + "AND version=?", (instrument_id, version)) if version
               else self.conn.execute(q + "ORDER BY version DESC LIMIT 1", (instrument_id,))).fetchone()
        return Instrument.from_dict(json.loads(row["record_json"])) if row else None

    # ---- three separate ledgers ----
    def create_account(self, kind: LedgerKind, name: str, actor: str = "system") -> LedgerAccount:
        now = self._clock()
        acct = LedgerAccount(f"{kind.value.lower()}-{uuid.uuid4().hex[:12]}", kind, name, now)
        self.conn.execute("INSERT INTO ledger_accounts VALUES (?,?,?,?)", (acct.account_id, kind.value, name, to_iso(now)))
        self.events.append(EventType.LEDGER_ACCOUNT_CREATED, "ledger", actor,
                           {"account_id": acct.account_id, "kind": kind.value, "name": name})
        return acct

    def list_accounts(self, kind: LedgerKind | None = None) -> list[LedgerAccount]:
        rows = self.conn.execute("SELECT * FROM ledger_accounts" + (" WHERE kind=?" if kind else "") + " ORDER BY created_at",
                                 (kind.value,) if kind else ()).fetchall()
        return [LedgerAccount(r["account_id"], LedgerKind(r["kind"]), r["name"], from_iso(r["created_at"])) for r in rows]

    # ---- data lineage ----
    def record_snapshot(self, snap: DataSnapshot, actor: str = "system") -> None:
        d = snap.to_dict()
        self.conn.execute("INSERT INTO data_snapshots VALUES (?,?,?,?,?,?,?)",
                          (d["snapshot_id"], d["source"], d["as_of"], d["ingested_at"], d["content_sha256"],
                           d["quality"], d["license_note"]))
        self.events.append(EventType.DATA_SNAPSHOT_RECORDED, snap.source, actor,
                           {"snapshot_id": snap.snapshot_id, "quality": d["quality"], "sha256": snap.content_sha256})
