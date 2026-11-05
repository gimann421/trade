-- NEXUS AIS schema v1. Portable SQL (SQLite now; Postgres later). Append-only where noted.

-- Immutable, hash-chained audit/event log (spec: Audit Engine, section 12.4).
CREATE TABLE events (
    seq             INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id        TEXT    NOT NULL UNIQUE,
    idempotency_key TEXT    UNIQUE,                 -- retry-safe appends
    event_type      TEXT    NOT NULL,
    occurred_at     TEXT    NOT NULL,               -- tz-aware ISO-8601 (UTC)
    recorded_at     TEXT    NOT NULL,               -- stamped by the system clock, not the caller
    source          TEXT    NOT NULL,
    actor           TEXT    NOT NULL,
    payload_json    TEXT    NOT NULL,
    prev_hash       TEXT    NOT NULL,
    hash            TEXT    NOT NULL UNIQUE
);
CREATE TRIGGER events_no_update BEFORE UPDATE ON events
BEGIN SELECT RAISE(ABORT, 'events are append-only'); END;
CREATE TRIGGER events_no_delete BEFORE DELETE ON events
BEGIN SELECT RAISE(ABORT, 'events are append-only'); END;

-- Instrument registry: versioned, append-only (tier changes create a new version).
CREATE TABLE instruments (
    instrument_id   TEXT    NOT NULL,
    version         INTEGER NOT NULL,
    asset_class     TEXT    NOT NULL,
    capability_tier TEXT    NOT NULL CHECK (capability_tier IN ('R0','R1','R2','R3')),  -- R4 unavailable at launch
    record_json     TEXT    NOT NULL,
    registered_at   TEXT    NOT NULL,
    PRIMARY KEY (instrument_id, version)
);
CREATE TRIGGER instruments_no_update BEFORE UPDATE ON instruments
BEGIN SELECT RAISE(ABORT, 'instruments are append-only'); END;
CREATE TRIGGER instruments_no_delete BEFORE DELETE ON instruments
BEGIN SELECT RAISE(ABORT, 'instruments are append-only'); END;

-- Three separate ledgers (spec 9.1). Kind is fixed at creation and can never change.
CREATE TABLE ledger_accounts (
    account_id  TEXT PRIMARY KEY,
    kind        TEXT NOT NULL CHECK (kind IN ('ACTUAL','SHADOW','PAPER_SLEEVE')),
    name        TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    UNIQUE (kind, name)
);
CREATE TRIGGER ledger_accounts_no_update BEFORE UPDATE ON ledger_accounts
BEGIN SELECT RAISE(ABORT, 'ledger accounts are immutable'); END;
CREATE TRIGGER ledger_accounts_no_delete BEFORE DELETE ON ledger_accounts
BEGIN SELECT RAISE(ABORT, 'ledger accounts are immutable'); END;

-- Source lineage for every data batch.
CREATE TABLE data_snapshots (
    snapshot_id    TEXT PRIMARY KEY,
    source         TEXT NOT NULL,
    as_of          TEXT NOT NULL,
    ingested_at    TEXT NOT NULL,
    content_sha256 TEXT NOT NULL,
    quality        TEXT NOT NULL CHECK (quality IN ('ok','stale','missing','conflicting','unverified')),
    license_note   TEXT
);
CREATE TRIGGER data_snapshots_no_update BEFORE UPDATE ON data_snapshots
BEGIN SELECT RAISE(ABORT, 'data snapshots are append-only'); END;
CREATE TRIGGER data_snapshots_no_delete BEFORE DELETE ON data_snapshots
BEGIN SELECT RAISE(ABORT, 'data snapshots are append-only'); END;
