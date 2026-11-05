"""Immutable, hash-chained audit/event store (the Audit Engine foundation)."""
from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

from .domain.enums import DECISION_LIKE_EVENTS, EventType
from .domain.models import canonical_json, content_hash
from .errors import AuditChainError, NexusError, SecretError
from .secrets import scan_text_for_secrets
from .timeutil import from_iso, require_aware, to_iso, utcnow

GENESIS_HASH = "0" * 64


@dataclass(frozen=True)
class Event:
    seq: int
    event_id: str
    idempotency_key: str | None
    event_type: EventType
    occurred_at: datetime
    recorded_at: datetime
    source: str
    actor: str
    payload: dict[str, Any]
    prev_hash: str
    hash: str


def _compute_hash(event_id, idem, etype, occurred, recorded, source, actor, payload_json, prev_hash) -> str:
    body = canonical_json({"event_id": event_id, "idempotency_key": idem, "event_type": etype,
                           "occurred_at": occurred, "recorded_at": recorded, "source": source,
                           "actor": actor, "payload": payload_json, "prev_hash": prev_hash})
    return content_hash(body)


class EventStore:
    def __init__(self, conn: sqlite3.Connection, clock: Callable[[], datetime] = utcnow,
                 clock_skew_tolerance_seconds: float = 5.0):
        self.conn = conn
        self._clock = clock
        self.skew = clock_skew_tolerance_seconds

    def append(self, event_type: EventType, source: str, actor: str, payload: dict[str, Any] | None = None,
               occurred_at: datetime | None = None, idempotency_key: str | None = None) -> Event:
        """Append one event. Retry-safe when ``idempotency_key`` is given.

        ``recorded_at`` always comes from the system clock. Decision-like events must carry an
        ``occurred_at`` within the skew tolerance of ``recorded_at`` - no backdating, no future dating.
        """
        if not isinstance(event_type, EventType):
            raise NexusError("event_type must be an EventType")
        payload = payload or {}
        payload_json = canonical_json(payload)
        if scan_text_for_secrets(payload_json) or scan_text_for_secrets(f"{source} {actor}"):
            raise SecretError("secret-like content refused in audit event")
        recorded = require_aware(self._clock(), "clock")
        occurred = require_aware(occurred_at, "occurred_at") if occurred_at is not None else recorded
        if event_type in DECISION_LIKE_EVENTS:
            if occurred_at is None:
                raise NexusError(f"{event_type.value} requires an explicit occurred_at")
            if abs((recorded - occurred).total_seconds()) > self.skew:
                raise NexusError(f"{event_type.value}: occurred_at differs from recorded_at by more than "
                                 f"{self.skew}s (backdating/future-dating refused)")
        self.conn.execute("BEGIN IMMEDIATE")  # serialize chain growth
        try:
            if idempotency_key is not None:
                row = self.conn.execute("SELECT * FROM events WHERE idempotency_key = ?", (idempotency_key,)).fetchone()
                if row is not None:
                    if (row["event_type"] != event_type.value or row["payload_json"] != payload_json
                            or row["source"] != source or row["actor"] != actor):
                        raise NexusError(f"idempotency key {idempotency_key!r} reused with different content")
                    self.conn.execute("COMMIT")
                    return self._row_to_event(row)
            last = self.conn.execute("SELECT hash FROM events ORDER BY seq DESC LIMIT 1").fetchone()
            prev = last["hash"] if last else GENESIS_HASH
            event_id = str(uuid.uuid4())
            occ_s, rec_s = to_iso(occurred), to_iso(recorded)
            h = _compute_hash(event_id, idempotency_key, event_type.value, occ_s, rec_s, source, actor, payload_json, prev)
            cur = self.conn.execute(
                "INSERT INTO events (event_id, idempotency_key, event_type, occurred_at, recorded_at, source, actor,"
                " payload_json, prev_hash, hash) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (event_id, idempotency_key, event_type.value, occ_s, rec_s, source, actor, payload_json, prev, h))
            row = self.conn.execute("SELECT * FROM events WHERE seq = ?", (cur.lastrowid,)).fetchone()
            self.conn.execute("COMMIT")
            return self._row_to_event(row)
        except Exception:
            if self.conn.in_transaction:
                self.conn.execute("ROLLBACK")
            raise

    @staticmethod
    def _row_to_event(r: sqlite3.Row) -> Event:
        import json
        return Event(r["seq"], r["event_id"], r["idempotency_key"], EventType(r["event_type"]),
                     from_iso(r["occurred_at"]), from_iso(r["recorded_at"]), r["source"], r["actor"],
                     json.loads(r["payload_json"]), r["prev_hash"], r["hash"])

    def all(self) -> list[Event]:
        return [self._row_to_event(r) for r in self.conn.execute("SELECT * FROM events ORDER BY seq")]

    def count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]

    def verify_chain(self) -> int:
        """Recompute the whole chain. Raises ``AuditChainError`` on any tamper; returns event count."""
        prev, n = GENESIS_HASH, 0
        for r in self.conn.execute("SELECT * FROM events ORDER BY seq"):
            n += 1
            if r["prev_hash"] != prev:
                raise AuditChainError(f"chain broken at seq {r['seq']}: prev_hash mismatch")
            expect = _compute_hash(r["event_id"], r["idempotency_key"], r["event_type"], r["occurred_at"],
                                   r["recorded_at"], r["source"], r["actor"], r["payload_json"], r["prev_hash"])
            if expect != r["hash"]:
                raise AuditChainError(f"event hash mismatch at seq {r['seq']}")
            prev = r["hash"]
        return n

    def append_correction(self, original_event_id: str, note: str, actor: str) -> Event:
        """Original records are never edited; corrections are appended and reference them."""
        exists = self.conn.execute("SELECT 1 FROM events WHERE event_id = ?", (original_event_id,)).fetchone()
        if not exists:
            raise NexusError("cannot correct an unknown event")
        return self.append(EventType.CORRECTION, "audit", actor, {"corrects": original_event_id, "note": note})
