from datetime import datetime, timedelta, timezone

import pytest

from nexus.config import load_config
from nexus.store import Store


class FakeClock:
    def __init__(self):
        self.now = datetime(2026, 11, 5, 12, 0, 0, tzinfo=timezone.utc)

    def __call__(self):
        return self.now

    def advance(self, **kw):
        self.now += timedelta(**kw)


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def store(clock):
    return Store(":memory:", load_config(), clock=clock)
