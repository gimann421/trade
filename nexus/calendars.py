"""Trading calendars. NYSE regular sessions are computed from the published holiday rules.

Limitation: ad hoc closures (national days of mourning, weather) are NOT modeled; they must be
added to ``ADHOC_CLOSURES`` when they occur. Unknown calendars fail closed.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from .errors import NexusError
from .timeutil import require_aware

NY = ZoneInfo("America/New_York")
ADHOC_CLOSURES: set[date] = {date(2025, 1, 9)}  # National Day of Mourning (Carter)


def _easter(y: int) -> date:
    a, b, c = y % 19, y // 100, y % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return date(y, month, day + 1)


def _nth_weekday(y: int, m: int, weekday: int, n: int) -> date:
    d = date(y, m, 1)
    d += timedelta(days=(weekday - d.weekday()) % 7)
    return d + timedelta(weeks=n - 1)


def _last_weekday(y: int, m: int, weekday: int) -> date:
    d = date(y + (m == 12), m % 12 + 1, 1) - timedelta(days=1)
    return d - timedelta(days=(d.weekday() - weekday) % 7)


def _observed(d: date) -> date | None:
    if d.weekday() == 5:
        return d - timedelta(days=1)
    if d.weekday() == 6:
        return d + timedelta(days=1)
    return d


def nyse_holidays(y: int) -> set[date]:
    h = {_nth_weekday(y, 1, 0, 3), _nth_weekday(y, 2, 0, 3), _easter(y) - timedelta(days=2),
         _last_weekday(y, 5, 0), _nth_weekday(y, 9, 0, 1), _nth_weekday(y, 11, 3, 4)}
    fixed = [date(y, 7, 4), date(y, 12, 25)] + ([date(y, 6, 19)] if y >= 2022 else [])
    h |= {_observed(d) for d in fixed}
    ny = date(y, 1, 1)
    if ny.weekday() != 5:  # a Saturday New Year is NOT observed on the prior Friday
        h.add(_observed(ny))
    return h | {d for d in ADHOC_CLOSURES if d.year == y}


class Calendar:
    name = "base"
    tz: ZoneInfo = ZoneInfo("UTC")

    def is_session(self, d: date) -> bool: raise NotImplementedError
    def session_close(self, d: date) -> datetime: raise NotImplementedError

    def last_completed_session(self, now: datetime, grace: timedelta = timedelta(0)) -> date | None:
        """Latest session whose close (+grace) is <= now. Searches back up to ~20 days."""
        now = require_aware(now, "now")
        d = now.astimezone(self.tz).date()
        for _ in range(20):
            if self.is_session(d) and self.session_close(d) + grace <= now:
                return d
            d -= timedelta(days=1)
        return None

    def sessions_between(self, start: date, end: date) -> list[date]:
        out, d = [], start
        while d <= end:
            if self.is_session(d):
                out.append(d)
            d += timedelta(days=1)
        return out


class NyseCalendar(Calendar):
    name = "XNYS"
    tz = NY

    def is_session(self, d: date) -> bool:
        return d.weekday() < 5 and d not in nyse_holidays(d.year)

    def is_early_close(self, d: date) -> bool:
        if not self.is_session(d):
            return False
        thanksgiving = _nth_weekday(d.year, 11, 3, 4)
        if d == thanksgiving + timedelta(days=1):
            return True
        if d == date(d.year, 12, 24):
            return True
        return d == date(d.year, 7, 3) and d.weekday() < 5 and date(d.year, 7, 4).weekday() != 0

    def session_close(self, d: date) -> datetime:
        if not self.is_session(d):
            raise NexusError(f"{d} is not an XNYS session")
        return datetime.combine(d, time(13, 0) if self.is_early_close(d) else time(16, 0), tzinfo=NY)

    def session_open(self, d: date) -> datetime:
        if not self.is_session(d):
            raise NexusError(f"{d} is not an XNYS session")
        return datetime.combine(d, time(9, 30), tzinfo=NY)

    def is_open(self, now: datetime) -> bool:
        now = require_aware(now, "now")
        d = now.astimezone(NY).date()
        return self.is_session(d) and self.session_open(d) <= now < self.session_close(d)


class AlwaysOpenCalendar(Calendar):
    """24/7 markets (digital assets). Daily bars close at 00:00 UTC."""
    name = "24x7"

    def is_session(self, d: date) -> bool:
        return True

    def session_close(self, d: date) -> datetime:
        return datetime.combine(d + timedelta(days=1), time(0, 0), tzinfo=timezone.utc)


_CALENDARS = {"XNYS": NyseCalendar(), "24x7": AlwaysOpenCalendar()}


def get_calendar(name: str) -> Calendar:
    try:
        return _CALENDARS[name]
    except KeyError:
        raise NexusError(f"unknown calendar {name!r}; no data can be treated as current") from None
