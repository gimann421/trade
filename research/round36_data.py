"""Data for round 36 (research/r36-value-yields-2026-10-29.md): shares outstanding from SEC XBRL and unadjusted closes.

    PYTHONPATH=. python research/round36_data.py shares   # data/round36/facts.csv  (cover-page and weighted diluted shares)
    PYTHONPATH=. python research/round36_data.py raw      # data/round36/raw/<ticker>_1Day.csv (split- and dividend-UNadjusted bars)

Market value at a 10-K filing date = shares x the raw close that day; later dates scale it by the adjusted-close ratio.
"""

import json
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import pandas as pd

from core.data import COLUMNS, DATA_DIR, bars_path, drop_incomplete_session, load_paper_keys
from core.edgar import HEADERS, load_constituents

OUT = DATA_DIR / "round36"
RAW = OUT / "raw"
CONCEPT = "https://data.sec.gov/api/xbrl/companyconcept/CIK{cik:010d}/{ns}/{tag}.json"
JOBS = (("dei", "EntityCommonStockSharesOutstanding"), ("us-gaap", "WeightedAverageNumberOfDilutedSharesOutstanding"))


def _one(symbol, cik, ns, tag):
    for attempt in range(3):
        try:
            req = urllib.request.Request(CONCEPT.format(cik=cik, ns=ns, tag=tag), headers=HEADERS)
            payload = json.loads(urllib.request.urlopen(req, timeout=60).read())
            return [{"symbol": symbol, "tag": tag, "start": r.get("start"), "end": r["end"], "val": r["val"], "form": r.get("form"),
                     "filed": r["filed"]} for r in payload["units"].get("shares", [])]
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None
            time.sleep(1 + attempt)
        except Exception:
            time.sleep(1 + attempt)
    return None


def fetch_shares(workers: int = 6) -> pd.DataFrame:
    OUT.mkdir(parents=True, exist_ok=True)
    jobs = [(s, c, ns, t) for s, c in sorted(load_constituents().items()) for ns, t in JOBS]
    rows = []
    with ThreadPoolExecutor(workers) as pool:
        for n, result in enumerate(pool.map(lambda j: _one(*j), jobs), 1):
            rows.extend(result or [])
            if n % 200 == 0:
                print(n, len(rows), flush=True)
    frame = pd.DataFrame(rows)
    frame.to_csv(OUT / "facts.csv", index=False)
    print(frame.groupby("tag").symbol.nunique().to_dict())
    return frame


def fetch_raw(pause: float = 0.35) -> None:
    from alpaca.data.enums import Adjustment
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame
    from core.universe import last_member_dates, load_membership
    keys = load_paper_keys()
    client = StockHistoricalDataClient(keys.api_key, keys.secret_key)
    RAW.mkdir(parents=True, exist_ok=True)
    end = datetime.now(timezone.utc) - pd.Timedelta(minutes=20)
    missing = []
    for ticker, asof in last_member_dates(load_membership()).items():
        if bars_path(ticker, RAW).exists():
            continue
        try:
            req = StockBarsRequest(symbol_or_symbols=ticker.upper(), timeframe=TimeFrame.Day, start=datetime(2016, 1, 1, tzinfo=timezone.utc),
                                   end=end, adjustment=Adjustment.RAW, asof=str(asof.date()))
            df = client.get_stock_bars(req).df
            if isinstance(df.index, pd.MultiIndex):
                df = df.xs(ticker.upper(), level="symbol")
            df.index = pd.to_datetime(df.index).tz_convert("America/New_York").date
            df.index.name = "date"
            drop_incomplete_session(df, end)[COLUMNS].to_csv(bars_path(ticker, RAW))
        except Exception as exc:
            missing.append((ticker, str(exc)[:80]))
        time.sleep(pause)
    print("missing", len(missing), missing[:10])


def load_facts() -> pd.DataFrame:
    return pd.read_csv(OUT / "facts.csv", parse_dates=["start", "end", "filed"])


if __name__ == "__main__":
    {"shares": fetch_shares, "raw": fetch_raw}[sys.argv[1]]()
