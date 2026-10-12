"""Hypothesis ledger: every idea, its status, and the evidence for or against it."""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from core.config import ROOT

LEDGER_PATH = ROOT / "memory" / "ledger.db"

STATUSES = ("proposed", "testing", "supported", "rejected", "retired")
EVIDENCE_KINDS = ("backtest", "paper", "note")
VERDICTS = ("supports", "contradicts", "inconclusive")

SCHEMA = f"""
CREATE TABLE IF NOT EXISTS hypotheses (
    id               INTEGER PRIMARY KEY,
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL,
    title            TEXT NOT NULL,
    statement        TEXT NOT NULL,   -- falsifiable claim
    rationale        TEXT,
    research_memo    TEXT,            -- path under research/
    strategy         TEXT,            -- file under strategies/, e.g. momentum_v2.py
    status           TEXT NOT NULL DEFAULT 'proposed'
                     CHECK (status IN {STATUSES})
);
CREATE TABLE IF NOT EXISTS evidence (
    id               INTEGER PRIMARY KEY,
    hypothesis_id    INTEGER NOT NULL REFERENCES hypotheses(id),
    created_at       TEXT NOT NULL,
    kind             TEXT NOT NULL CHECK (kind IN {EVIDENCE_KINDS}),
    ref              TEXT,            -- path under backtests/ or journal/
    summary          TEXT NOT NULL,
    verdict          TEXT NOT NULL CHECK (verdict IN {VERDICTS})
);
CREATE INDEX IF NOT EXISTS evidence_hypothesis ON evidence(hypothesis_id);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(path: Path = LEDGER_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


def add_hypothesis(conn, title, statement, rationale=None, research_memo=None, strategy=None) -> int:
    now = _now()
    with conn:
        cur = conn.execute(
            "INSERT INTO hypotheses (created_at, updated_at, title, statement, rationale, research_memo, strategy)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (now, now, title, statement, rationale, research_memo, strategy),
        )
    return cur.lastrowid


def set_status(conn, hypothesis_id: int, status: str) -> None:
    with conn:
        cur = conn.execute("UPDATE hypotheses SET status = ?, updated_at = ? WHERE id = ?",
                           (status, _now(), hypothesis_id))
    if cur.rowcount == 0:
        raise KeyError(hypothesis_id)


def add_evidence(conn, hypothesis_id: int, kind: str, summary: str, verdict: str, ref=None) -> int:
    with conn:
        cur = conn.execute(
            "INSERT INTO evidence (hypothesis_id, created_at, kind, ref, summary, verdict)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (hypothesis_id, _now(), kind, ref, summary, verdict),
        )
    return cur.lastrowid


if __name__ == "__main__":
    connect().close()
    print(f"ledger ready at {LEDGER_PATH.relative_to(ROOT)}")
