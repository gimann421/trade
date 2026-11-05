-- Daily bars with full lineage. Append-only; every row belongs to a data snapshot.
CREATE TABLE bars (
    snapshot_id   TEXT    NOT NULL REFERENCES data_snapshots(snapshot_id),
    instrument_id TEXT    NOT NULL,
    session_date  TEXT    NOT NULL,           -- YYYY-MM-DD in the instrument's calendar
    open          REAL    NOT NULL,
    high          REAL    NOT NULL,
    low           REAL    NOT NULL,
    close         REAL    NOT NULL,
    volume        REAL    NOT NULL,
    PRIMARY KEY (snapshot_id, instrument_id, session_date)
);
CREATE INDEX bars_instrument_date ON bars (instrument_id, session_date);
CREATE TRIGGER bars_no_update BEFORE UPDATE ON bars
BEGIN SELECT RAISE(ABORT, 'bars are append-only'); END;
CREATE TRIGGER bars_no_delete BEFORE DELETE ON bars
BEGIN SELECT RAISE(ABORT, 'bars are append-only'); END;
