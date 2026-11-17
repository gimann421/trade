-- Portfolio accounting. Quantities and money are stored as exact decimal TEXT (never floats).

-- Journal of cash/position movements for SHADOW and PAPER_SLEEVE accounts (and owner-confirmed ACTUAL
-- transactions). Append-only. 'origin' must match the account kind, enforced by trigger, so a simulated
-- entry can never land in the actual ledger and vice versa.
CREATE TABLE ledger_entries (
    entry_id      TEXT PRIMARY KEY,
    account_id    TEXT NOT NULL REFERENCES ledger_accounts(account_id),
    occurred_at   TEXT NOT NULL,
    recorded_at   TEXT NOT NULL,
    kind          TEXT NOT NULL CHECK (kind IN ('OPENING','DEPOSIT','WITHDRAWAL','TRADE','FEE','DIVIDEND','SPLIT','ADJUSTMENT')),
    origin        TEXT NOT NULL CHECK (origin IN ('owner_confirmed','simulated')),
    instrument_id TEXT,
    qty_delta     TEXT NOT NULL,
    cash_delta    TEXT NOT NULL,
    price         TEXT,
    fee           TEXT NOT NULL DEFAULT '0',
    ref           TEXT,                       -- snapshot id, order id, etc.
    note          TEXT
);
CREATE INDEX ledger_entries_account ON ledger_entries (account_id, occurred_at);
CREATE TRIGGER ledger_entries_origin_matches_kind BEFORE INSERT ON ledger_entries
WHEN (SELECT kind FROM ledger_accounts WHERE account_id = NEW.account_id) = 'ACTUAL' AND NEW.origin <> 'owner_confirmed'
BEGIN SELECT RAISE(ABORT, 'simulated entries may never enter the ACTUAL ledger'); END;
CREATE TRIGGER ledger_entries_sim_origin BEFORE INSERT ON ledger_entries
WHEN (SELECT kind FROM ledger_accounts WHERE account_id = NEW.account_id) <> 'ACTUAL' AND NEW.origin <> 'simulated'
BEGIN SELECT RAISE(ABORT, 'owner-confirmed entries may only enter the ACTUAL ledger'); END;
CREATE TRIGGER ledger_entries_no_update BEFORE UPDATE ON ledger_entries
BEGIN SELECT RAISE(ABORT, 'ledger entries are append-only'); END;
CREATE TRIGGER ledger_entries_no_delete BEFORE DELETE ON ledger_entries
BEGIN SELECT RAISE(ABORT, 'ledger entries are append-only'); END;

-- Immutable portfolio snapshots (actual imports, shadow openings). A change creates a new snapshot.
CREATE TABLE portfolio_snapshots (
    snapshot_id   TEXT PRIMARY KEY,
    account_id    TEXT NOT NULL REFERENCES ledger_accounts(account_id),
    as_of         TEXT NOT NULL,
    recorded_at   TEXT NOT NULL,
    source        TEXT NOT NULL,              -- e.g. 'broker statement 2026-11-17'
    confirmed_by  TEXT,                       -- owner confirmation for ACTUAL snapshots
    cash_json     TEXT NOT NULL,
    holdings_json TEXT NOT NULL,
    estimated_json TEXT NOT NULL,             -- fields that are missing/estimated, flagged
    open_orders_json TEXT NOT NULL,
    content_sha256 TEXT NOT NULL,
    supersedes    TEXT REFERENCES portfolio_snapshots(snapshot_id)
);
CREATE TRIGGER portfolio_snapshots_no_update BEFORE UPDATE ON portfolio_snapshots
BEGIN SELECT RAISE(ABORT, 'portfolio snapshots are immutable'); END;
CREATE TRIGGER portfolio_snapshots_no_delete BEFORE DELETE ON portfolio_snapshots
BEGIN SELECT RAISE(ABORT, 'portfolio snapshots are immutable'); END;
