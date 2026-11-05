"""Deterministic in-memory/CSV adapter for development and tests. No vendor entitlement is assumed."""
from __future__ import annotations

import csv
from datetime import date, datetime
from pathlib import Path
from typing import Callable

from ..domain.models import Bar
from ..timeutil import utcnow
from .base import FetchResult


class FixtureAdapter:
    def __init__(self, bars: list[Bar], source: str = "fixture", as_of: datetime | None = None,
                 clock: Callable[[], datetime] = utcnow):
        self.source = source
        self._bars = list(bars)
        self._as_of = as_of
        self._clock = clock

    @classmethod
    def from_csv(cls, path: str | Path, instrument_id: str, **kw) -> "FixtureAdapter":
        with open(path, newline="", encoding="utf-8") as f:
            bars = [Bar(instrument_id, r["date"], float(r["open"]), float(r["high"]), float(r["low"]),
                        float(r["close"]), float(r["volume"])) for r in csv.DictReader(f)]
        return cls(bars, **kw)

    def fetch_daily_bars(self, instrument_id: str, start: date, end: date) -> FetchResult:
        now = self._clock()
        sel = [b for b in self._bars if b.instrument_id == instrument_id
               and start.isoformat() <= b.session_date <= end.isoformat()]
        return FetchResult(self.source, self._as_of or now, now, sel, "synthetic fixture data")
