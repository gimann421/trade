from datetime import date

import pytest

from nexus.adapters.alpaca_data import AlpacaDataAdapter, assert_data_url, data_credentials, urllib_get
from nexus.domain import AssetClass, Instrument
from nexus.errors import LaunchBoundaryViolation, SecretError, StaleOrInvalidDataError
from nexus.ingestion import ingest_daily_bars
from nexus.secrets import Secret

IID = "EQ:XNAS:AAPL"


def mk(transport, clock):
    a = AlpacaDataAdapter(Secret("k", "keyvalue123456"), Secret("s", "secretvalue123456"), transport=transport, clock=clock)
    a.register_symbol(IID, "AAPL")
    return a


def page(days, token=None):
    return {"bars": [{"t": f"2026-11-0{d}T05:00:00Z", "o": 100, "h": 101, "l": 99, "c": 100.5, "v": 10} for d in days],
            "next_page_token": token}


def test_pagination_and_session_dates(clock):
    pages = iter([page([2, 3], "tok"), page([4, 5, 6])])
    urls = []
    def t(url, headers):
        urls.append(url)
        return next(pages)
    r = mk(t, clock).fetch_daily_bars(IID, date(2026, 11, 2), date(2026, 11, 6))
    assert [b.session_date for b in r.bars] == [f"2026-11-0{d}" for d in range(2, 7)]
    assert "page_token=tok" in urls[1] and "feed=iex" in urls[0] and "adjustment=all" in urls[0]
    assert r.fetched_at.tzinfo


def test_full_ingest_with_fake_transport(store, clock):
    store.register_instrument(Instrument(IID, {"alpaca": "AAPL"}, AssetClass.EQUITY, "USD", "America/New_York"))
    snap, rep = ingest_daily_bars(store, mk(lambda u, h: page([2, 3, 4, 5, 6]), clock), IID, date(2026, 11, 2), date(2026, 11, 6))
    assert rep.ok and snap.source == "alpaca-data"


@pytest.mark.parametrize("body", [{}, {"bars": [{"t": "bad"}]}, None])
def test_malformed_responses_fail_closed(clock, body):
    with pytest.raises(StaleOrInvalidDataError):
        mk(lambda u, h: body, clock).fetch_daily_bars(IID, date(2026, 11, 2), date(2026, 11, 6))


def test_unmapped_symbol_and_endless_pagination_fail_closed(clock):
    a = mk(lambda u, h: page([2], "same"), clock)
    with pytest.raises(StaleOrInvalidDataError):
        a.fetch_daily_bars(IID, date(2026, 11, 2), date(2026, 11, 6))
    with pytest.raises(StaleOrInvalidDataError):
        a.fetch_daily_bars("EQ:XNAS:ZZZ", date(2026, 11, 2), date(2026, 11, 6))


@pytest.mark.parametrize("url", ["https://api.alpaca.markets/v2/orders", "https://paper-api.alpaca.markets/v2/orders",
                                 "http://data.alpaca.markets/x", "https://data.alpaca.markets.evil.com/x"])
def test_only_data_host_reachable(url):
    with pytest.raises(LaunchBoundaryViolation):
        assert_data_url(url)
    with pytest.raises(LaunchBoundaryViolation):
        urllib_get(url, {})


def test_credentials_env_only_with_fallback():
    assert data_credentials({"NEXUS_ALPACA_DATA_KEY_ID": "aaaaaa11", "NEXUS_ALPACA_DATA_SECRET_KEY": "bbbbbb22"})
    k, _ = data_credentials({"ALPACA_PAPER_API_KEY": "cccccc33", "ALPACA_PAPER_SECRET_KEY": "dddddd44"})
    assert "cccccc" not in repr(k)
    with pytest.raises(SecretError):
        data_credentials({})


def test_adapter_has_no_write_methods():
    assert not [n for n in dir(AlpacaDataAdapter) if any(v in n for v in ("order", "post", "put", "delete", "cancel"))]
