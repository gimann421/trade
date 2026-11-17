"""Read-only Alpaca market-data adapter (daily bars).

Only HTTP GET to https://data.alpaca.markets is possible: the default transport refuses any other
method or host. No entitlement is assumed: the default feed is the free ``iex`` feed (partial volume);
choose ``sip`` only if the account is entitled. Any error or malformed response fails closed.
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from typing import Callable
from zoneinfo import ZoneInfo

from ..domain.models import Bar
from ..errors import LaunchBoundaryViolation, StaleOrInvalidDataError
from ..secrets import Secret, get_secret
from ..timeutil import utcnow
from .base import FetchResult

DATA_HOST = "data.alpaca.markets"
NY = ZoneInfo("America/New_York")
Transport = Callable[[str, dict[str, str]], dict]   # (url, headers) -> parsed JSON; GET only by construction


def data_credentials(environ: dict[str, str] | None = None) -> tuple[Secret, Secret]:
    """NEXUS-specific names first; falls back to the existing paper key names (read-only use only)."""
    import os
    env = os.environ if environ is None else environ
    pairs = [("NEXUS_ALPACA_DATA_KEY_ID", "NEXUS_ALPACA_DATA_SECRET_KEY"),
             ("ALPACA_PAPER_API_KEY", "ALPACA_PAPER_SECRET_KEY")]
    for k, s in pairs:
        if env.get(k) and env.get(s):
            return get_secret(k, env), get_secret(s, env)
    return get_secret(pairs[0][0], env), get_secret(pairs[0][1], env)  # raises SecretError


def assert_data_url(url: str) -> None:
    u = urllib.parse.urlsplit(url)
    if not (u.scheme == "https" and u.hostname == DATA_HOST and u.username is None and u.port is None):
        raise LaunchBoundaryViolation("data adapter may only call https://data.alpaca.markets")


def urllib_get(url: str, headers: dict[str, str]) -> dict:
    assert_data_url(url)
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 (host asserted above)
            return json.loads(resp.read().decode("utf-8"))
    except Exception as exc:  # network/HTTP/JSON: never swallow into empty data
        raise StaleOrInvalidDataError(f"alpaca data request failed: {type(exc).__name__}") from None


class AlpacaDataAdapter:
    source = "alpaca-data"

    def __init__(self, key_id: Secret, secret: Secret, feed: str = "iex", transport: Transport = urllib_get,
                 clock: Callable[[], datetime] = utcnow, symbol_key: str = "alpaca"):
        if feed not in ("iex", "sip"):
            raise ValueError("feed must be 'iex' or 'sip'")
        self._k, self._s, self.feed, self._get, self._clock, self._symkey = key_id, secret, feed, transport, clock, symbol_key
        self.symbols: dict[str, str] = {}   # instrument_id -> vendor symbol (set via register_symbol)

    def register_symbol(self, instrument_id: str, symbol: str) -> None:
        self.symbols[instrument_id] = symbol

    def fetch_daily_bars(self, instrument_id: str, start: date, end: date) -> FetchResult:
        sym = self.symbols.get(instrument_id)
        if not sym:
            raise StaleOrInvalidDataError(f"no Alpaca symbol mapped for {instrument_id}")
        headers = {"APCA-API-KEY-ID": self._k.reveal(), "APCA-API-SECRET-KEY": self._s.reveal(),
                   "accept": "application/json"}
        bars: list[Bar] = []
        token = None
        for _ in range(100):  # hard page cap
            q = {"timeframe": "1Day", "start": start.isoformat(), "end": end.isoformat(),
                 "adjustment": "all", "feed": self.feed, "limit": "10000"}
            if token:
                q["page_token"] = token
            url = f"https://{DATA_HOST}/v2/stocks/{urllib.parse.quote(sym)}/bars?{urllib.parse.urlencode(q)}"
            assert_data_url(url)
            body = self._get(url, headers)
            if not isinstance(body, dict) or "bars" not in body:
                raise StaleOrInvalidDataError("alpaca response missing 'bars'")
            for r in body["bars"] or []:
                try:
                    ts = datetime.fromisoformat(r["t"].replace("Z", "+00:00"))
                    d = ts.astimezone(NY).date().isoformat()
                    bars.append(Bar(instrument_id, d, r["o"], r["h"], r["l"], r["c"], r["v"]))
                except (KeyError, ValueError, TypeError):
                    raise StaleOrInvalidDataError("malformed bar in alpaca response") from None
            token = body.get("next_page_token")
            if not token:
                break
        else:
            raise StaleOrInvalidDataError("alpaca pagination did not terminate")
        now = self._clock()
        return FetchResult(self.source, now, now, bars, f"Alpaca market data, feed={self.feed}; check your plan's terms")
