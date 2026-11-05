from datetime import date, datetime, timedelta, timezone

import pytest

from nexus.calendars import AlwaysOpenCalendar, NY, NyseCalendar, get_calendar, nyse_holidays
from nexus.errors import NexusError

cal = NyseCalendar()


@pytest.mark.parametrize("d", [date(2026, 1, 1), date(2026, 1, 19), date(2026, 2, 16), date(2026, 4, 3),
                               date(2026, 5, 25), date(2026, 6, 19), date(2026, 7, 3), date(2026, 9, 7),
                               date(2026, 11, 26), date(2026, 12, 25), date(2027, 12, 24), date(2024, 3, 29),
                               date(2023, 1, 2)])
def test_known_nyse_holidays_are_closed(d):
    assert not cal.is_session(d)


@pytest.mark.parametrize("d", [date(2021, 12, 31), date(2026, 11, 27), date(2026, 11, 25), date(2026, 12, 24)])
def test_known_open_days(d):
    assert cal.is_session(d)


def test_weekends_closed_and_juneteenth_only_from_2022():
    assert not cal.is_session(date(2026, 11, 7))
    assert date(2021, 6, 18) not in nyse_holidays(2021) and cal.is_session(date(2021, 6, 18))


def test_early_closes():
    assert cal.session_close(date(2026, 11, 27)).hour == 13
    assert cal.session_close(date(2026, 12, 24)).hour == 13
    assert cal.session_close(date(2026, 11, 4)).hour == 16


def test_is_open_respects_timezone_and_dst():
    assert cal.is_open(datetime(2026, 11, 4, 14, 30, tzinfo=timezone.utc))    # 09:30 EST
    assert not cal.is_open(datetime(2026, 11, 4, 14, 29, tzinfo=timezone.utc))
    assert cal.is_open(datetime(2026, 7, 1, 13, 30, tzinfo=timezone.utc))     # 09:30 EDT
    assert not cal.is_open(datetime(2026, 11, 4, 21, 0, tzinfo=timezone.utc))  # 16:00 EST close
    with pytest.raises(NexusError):
        cal.is_open(datetime(2026, 11, 4, 15, 0))


def test_last_completed_session_with_grace_weekend_and_holiday():
    fri_after = datetime(2026, 11, 6, 21, 30, tzinfo=timezone.utc)
    assert cal.last_completed_session(fri_after) == date(2026, 11, 6)
    assert cal.last_completed_session(fri_after, timedelta(hours=1)) == date(2026, 11, 5)
    sunday = datetime(2026, 11, 8, 15, 0, tzinfo=timezone.utc)
    assert cal.last_completed_session(sunday) == date(2026, 11, 6)
    day_after_thanksgiving_morning = datetime(2026, 11, 27, 15, 0, tzinfo=timezone.utc)
    assert cal.last_completed_session(day_after_thanksgiving_morning) == date(2026, 11, 25)


def test_24x7_and_unknown_calendar():
    assert AlwaysOpenCalendar().is_session(date(2026, 11, 7))
    assert get_calendar("24x7").last_completed_session(datetime(2026, 11, 7, 12, tzinfo=timezone.utc)) == date(2026, 11, 6)
    with pytest.raises(NexusError):
        get_calendar("XLON")
