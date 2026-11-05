"""Timezone-safe time helpers. Naive datetimes are rejected everywhere."""
from __future__ import annotations

from datetime import datetime, timezone

from .errors import NexusError


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def require_aware(dt: datetime, what: str = "timestamp") -> datetime:
    if not isinstance(dt, datetime):
        raise NexusError(f"{what} must be a datetime, got {type(dt).__name__}")
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        raise NexusError(f"{what} must be timezone-aware (naive datetimes are rejected)")
    return dt


def to_iso(dt: datetime) -> str:
    """Canonical UTC ISO-8601 with microseconds, e.g. 2026-11-05T01:40:12.000000+00:00."""
    return require_aware(dt).astimezone(timezone.utc).isoformat(timespec="microseconds")


def from_iso(s: str) -> datetime:
    return require_aware(datetime.fromisoformat(s), "iso timestamp")
