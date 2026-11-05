"""Deterministic data-quality checks. These cannot be overridden by an LLM or by configuration."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from .calendars import Calendar
from .domain.enums import DataQuality
from .domain.models import Bar
from .errors import StaleOrInvalidDataError


@dataclass
class QualityReport:
    quality: DataQuality = DataQuality.OK
    issues: list[str] = field(default_factory=list)

    def fail(self, q: DataQuality, msg: str) -> None:
        self.issues.append(msg)
        order = [DataQuality.OK, DataQuality.UNVERIFIED, DataQuality.STALE, DataQuality.MISSING, DataQuality.CONFLICTING]
        if order.index(q) > order.index(self.quality):
            self.quality = q

    @property
    def ok(self) -> bool:
        return self.quality is DataQuality.OK

    def require_ok(self) -> None:
        if not self.ok:
            raise StaleOrInvalidDataError(f"data quality {self.quality.value}: {'; '.join(self.issues[:5])}")


def check_bars(bars: list[Bar], calendar: Calendar, start: date, end: date) -> QualityReport:
    """Structural checks: sanity, duplicates, and gaps against the trading calendar."""
    rep = QualityReport()
    seen: set[str] = set()
    for b in bars:
        vals = (b.open, b.high, b.low, b.close, b.volume)
        if any(not math.isfinite(v) for v in vals):
            rep.fail(DataQuality.CONFLICTING, f"{b.session_date}: non-finite value")
            continue
        if min(b.open, b.high, b.low, b.close) <= 0 or b.volume < 0:
            rep.fail(DataQuality.CONFLICTING, f"{b.session_date}: non-positive price or negative volume")
        if b.high < max(b.open, b.close, b.low) or b.low > min(b.open, b.close, b.high):
            rep.fail(DataQuality.CONFLICTING, f"{b.session_date}: OHLC inconsistent")
        if b.session_date in seen:
            rep.fail(DataQuality.CONFLICTING, f"{b.session_date}: duplicate bar")
        seen.add(b.session_date)
        try:
            d = date.fromisoformat(b.session_date)
        except ValueError:
            rep.fail(DataQuality.CONFLICTING, f"{b.session_date}: bad date")
            continue
        if not calendar.is_session(d):
            rep.fail(DataQuality.CONFLICTING, f"{b.session_date}: bar on a non-session day")
    expected = {d.isoformat() for d in calendar.sessions_between(start, end)}
    missing = sorted(expected - seen)
    if missing:
        rep.fail(DataQuality.MISSING, f"{len(missing)} missing session(s), first {missing[0]}")
    return rep


def check_sources_agree(a: list[Bar], b: list[Bar], rel_tol: float = 0.005) -> QualityReport:
    """Two independent sources must agree on closes within ``rel_tol`` or the data is contradictory."""
    rep = QualityReport()
    bm = {x.session_date: x for x in b}
    for x in a:
        y = bm.get(x.session_date)
        if y is not None and abs(x.close - y.close) > rel_tol * max(abs(x.close), abs(y.close)):
            rep.fail(DataQuality.CONFLICTING, f"{x.session_date}: close {x.close} vs {y.close}")
    return rep


def check_fresh(latest_session_date: str | None, calendar: Calendar, now: datetime,
                grace: timedelta) -> QualityReport:
    """Latest bar must be the most recent *completed* session (after grace). Otherwise stale."""
    rep = QualityReport()
    expected = calendar.last_completed_session(now, grace)
    if expected is None:
        rep.fail(DataQuality.UNVERIFIED, "cannot determine the expected latest session")
    elif latest_session_date is None:
        rep.fail(DataQuality.MISSING, "no bars at all")
    elif latest_session_date < expected.isoformat():
        rep.fail(DataQuality.STALE, f"latest bar {latest_session_date} older than expected {expected}")
    return rep
