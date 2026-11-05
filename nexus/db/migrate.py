"""Forward-only SQL migrations with checksum verification (migrations are never edited)."""
from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

from ..errors import NexusError
from ..timeutil import to_iso, utcnow

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def connect(path: str | Path) -> sqlite3.Connection:
    if str(path) != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), isolation_level=None)  # explicit transactions
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _migrations(directory: Path) -> list[tuple[int, str, str]]:
    out = []
    for p in sorted(directory.glob("*.sql")):
        version = int(p.name.split("_", 1)[0])
        out.append((version, p.name, p.read_text(encoding="utf-8")))
    versions = [v for v, _, _ in out]
    if versions != list(range(1, len(versions) + 1)):
        raise NexusError(f"migration versions must be contiguous from 1, got {versions}")
    return out


def migrate(conn: sqlite3.Connection, directory: Path = MIGRATIONS_DIR) -> list[int]:
    """Apply pending migrations atomically; return versions applied. Idempotent."""
    conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations ("
                 "version INTEGER PRIMARY KEY, name TEXT NOT NULL, sha256 TEXT NOT NULL, applied_at TEXT NOT NULL)")
    applied = {r["version"]: r["sha256"] for r in conn.execute("SELECT version, sha256 FROM schema_migrations")}
    newly = []
    for version, name, sql in _migrations(directory):
        digest = hashlib.sha256(sql.encode("utf-8")).hexdigest()
        if version in applied:
            if applied[version] != digest:
                raise NexusError(f"migration {name} was modified after being applied")
            continue
        conn.execute("BEGIN")
        try:
            for stmt in _split(sql):
                conn.execute(stmt)
            conn.execute("INSERT INTO schema_migrations VALUES (?,?,?,?)", (version, name, digest, to_iso(utcnow())))
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        newly.append(version)
    return newly


def _split(sql: str) -> list[str]:
    """Split on ';' outside CREATE TRIGGER ... END blocks."""
    stmts, buf, in_trigger = [], [], False
    for line in sql.splitlines():
        s = line.strip()
        if not s or s.startswith("--"):
            continue
        buf.append(line)
        if s.upper().startswith("CREATE TRIGGER"):
            in_trigger = True
        if in_trigger:
            if s.upper().rstrip(";") == "END" or s.upper().endswith("END;"):
                stmts.append("\n".join(buf)); buf, in_trigger = [], False
        elif s.endswith(";"):
            stmts.append("\n".join(buf)); buf = []
    if buf:
        stmts.append("\n".join(buf))
    return stmts
