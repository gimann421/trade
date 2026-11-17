-- Job execution history. Append-only; state is derived from the last event. Missed jobs are recorded, never implied to have run.
CREATE TABLE job_events (
    seq           INTEGER PRIMARY KEY AUTOINCREMENT,
    job_name      TEXT NOT NULL,
    scheduled_for TEXT NOT NULL,
    attempt       INTEGER NOT NULL,
    kind          TEXT NOT NULL CHECK (kind IN ('started','succeeded','failed','missed','skipped_halted','skipped_paused')),
    at            TEXT NOT NULL,
    detail_json   TEXT NOT NULL
);
CREATE INDEX job_events_job ON job_events (job_name, scheduled_for, seq);
CREATE TRIGGER job_events_no_update BEFORE UPDATE ON job_events BEGIN SELECT RAISE(ABORT, 'job events are append-only'); END;
CREATE TRIGGER job_events_no_delete BEFORE DELETE ON job_events BEGIN SELECT RAISE(ABORT, 'job events are append-only'); END;
