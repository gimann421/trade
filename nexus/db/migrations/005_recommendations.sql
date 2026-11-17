-- Advisory recommendations about the owner's real portfolio. Suggestions only: nothing here can place an order.
CREATE TABLE recommendations (
    rec_id        TEXT PRIMARY KEY,
    created_at    TEXT NOT NULL,
    account_id    TEXT NOT NULL REFERENCES ledger_accounts(account_id),
    snapshot_id   TEXT NOT NULL REFERENCES portfolio_snapshots(snapshot_id),
    kind          TEXT NOT NULL,
    subject       TEXT NOT NULL,
    severity      TEXT NOT NULL CHECK (severity IN ('info','watch','act')),
    summary       TEXT NOT NULL,
    evidence_json TEXT NOT NULL,
    generator     TEXT NOT NULL,                  -- deterministic generator name + version
    decision_event_id TEXT NOT NULL,
    UNIQUE (snapshot_id, kind, subject)           -- retry-safe: same finding on the same snapshot is recorded once
);
CREATE TRIGGER recommendations_no_update BEFORE UPDATE ON recommendations BEGIN SELECT RAISE(ABORT, 'recommendations are immutable'); END;
CREATE TRIGGER recommendations_no_delete BEFORE DELETE ON recommendations BEGIN SELECT RAISE(ABORT, 'recommendations are immutable'); END;

-- Outcome notes and owner responses are appended, never edited in.
CREATE TABLE recommendation_notes (
    seq     INTEGER PRIMARY KEY AUTOINCREMENT,
    rec_id  TEXT NOT NULL REFERENCES recommendations(rec_id),
    at      TEXT NOT NULL,
    author  TEXT NOT NULL,
    kind    TEXT NOT NULL CHECK (kind IN ('owner_response','outcome','correction')),
    note    TEXT NOT NULL
);
CREATE TRIGGER recommendation_notes_no_update BEFORE UPDATE ON recommendation_notes BEGIN SELECT RAISE(ABORT, 'notes are append-only'); END;
CREATE TRIGGER recommendation_notes_no_delete BEFORE DELETE ON recommendation_notes BEGIN SELECT RAISE(ABORT, 'notes are append-only'); END;
