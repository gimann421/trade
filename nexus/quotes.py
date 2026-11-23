"""Secondary read-only quote source (Yahoo daily chart) for holdings the primary feed does not cover, e.g. OTC names.
Read-only market data, no account access. Used only as a labelled fallback; the caller records which source priced what."""
from __future__ import annotations

import json
import urllib.request
from datetime import date, datetime, timezone
from decimal import Decimal

URL = "https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range=10d&interval=1d"


def yahoo_last_close(symbol: str, timeout: float = 15.0) -> tuple[Decimal, str] | None:
    """Latest non-null daily close and its session date, or None when the feed has nothing usable."""
    try:
        req = urllib.request.Request(URL.format(sym=symbol), headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            res = json.load(r)["chart"]["result"][0]
        ts, closes = res["timestamp"], res["indicators"]["quote"][0]["close"]
        off = int(res["meta"].get("gmtoffset", 0))
        rows = [(datetime.fromtimestamp(t + off, timezone.utc).date(), c) for t, c in zip(ts, closes) if c]
        if not rows:
            return None
        d, c = max(rows)
        return (Decimal(str(round(c, 4))), d.isoformat()) if c > 0 else None
    except Exception:
        return None
