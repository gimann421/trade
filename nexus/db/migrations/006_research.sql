-- Hypothesis registry, experiments and independent promotion decisions. All append-only.
CREATE TABLE hypotheses (
    hyp_id        TEXT NOT NULL,
    version       INTEGER NOT NULL,
    author        TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    record_json   TEXT NOT NULL,
    record_sha    TEXT NOT NULL,
    event_id      TEXT NOT NULL,
    PRIMARY KEY (hyp_id, version)
);
CREATE TRIGGER hypotheses_no_update BEFORE UPDATE ON hypotheses BEGIN SELECT RAISE(ABORT, 'hypotheses are immutable'); END;
CREATE TRIGGER hypotheses_no_delete BEFORE DELETE ON hypotheses BEGIN SELECT RAISE(ABORT, 'hypotheses are immutable'); END;

CREATE TABLE experiments (
    exp_id        TEXT PRIMARY KEY,
    hyp_id        TEXT NOT NULL,
    version       INTEGER NOT NULL,
    segment       TEXT NOT NULL CHECK (segment IN ('train','validation','holdout')),
    created_at    TEXT NOT NULL,
    code_commit   TEXT NOT NULL,
    config_sha    TEXT NOT NULL,
    snapshot_ids  TEXT NOT NULL,
    result_json   TEXT NOT NULL,
    result_sha    TEXT NOT NULL,
    FOREIGN KEY (hyp_id, version) REFERENCES hypotheses(hyp_id, version)
);
-- The untouched holdout may be evaluated once per hypothesis version.
CREATE UNIQUE INDEX experiments_one_holdout ON experiments (hyp_id, version) WHERE segment = 'holdout';
CREATE TRIGGER experiments_no_update BEFORE UPDATE ON experiments BEGIN SELECT RAISE(ABORT, 'experiments are immutable'); END;
CREATE TRIGGER experiments_no_delete BEFORE DELETE ON experiments BEGIN SELECT RAISE(ABORT, 'experiments are immutable'); END;

CREATE TABLE promotion_decisions (
    seq         INTEGER PRIMARY KEY AUTOINCREMENT,
    hyp_id      TEXT NOT NULL,
    version     INTEGER NOT NULL,
    from_tier   TEXT NOT NULL,
    to_tier     TEXT NOT NULL,
    decision    TEXT NOT NULL CHECK (decision IN ('pass','fail','defer')),
    decided_at  TEXT NOT NULL,
    decided_by  TEXT NOT NULL,
    role        TEXT NOT NULL,
    reasons     TEXT NOT NULL,
    evidence_json TEXT NOT NULL,
    FOREIGN KEY (hyp_id, version) REFERENCES hypotheses(hyp_id, version)
);
CREATE TRIGGER promotion_no_update BEFORE UPDATE ON promotion_decisions BEGIN SELECT RAISE(ABORT, 'promotion decisions are append-only'); END;
CREATE TRIGGER promotion_no_delete BEFORE DELETE ON promotion_decisions BEGIN SELECT RAISE(ABORT, 'promotion decisions are append-only'); END;
