from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol

from ..domain.models import Bar


@dataclass(frozen=True)
class FetchResult:
    source: str
    as_of: datetime            # time the data describes (tz-aware)
    fetched_at: datetime       # when it was received (tz-aware)
    bars: list[Bar]
    license_note: str | None = None


class MarketDataAdapter(Protocol):
    """Read-only. Adapters never write to any external system."""
    source: str

    def fetch_daily_bars(self, instrument_id: str, start: date, end: date) -> FetchResult: ...
