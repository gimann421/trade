"""Late-session snapshots of member prices from Alpaca 15-minute bars.

Per ticker and session, three numbers are kept (data/intraday/<TICKER>.csv):
  p1530  close of the 15:15-15:30 bar (the price at 15:30)
  p1545  close of the 15:30-15:45 bar (the price at 15:45)
  vol1545  total volume of the bars starting from 09:30 up to and including 15:30
Prices are split- and dividend-adjusted (adjustment ALL) like the daily files.

    python -m core.intraday download [--workers 4]
"""

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone

import pandas as pd

from core.config import ROOT, load_paper_keys
from core.data import DATA_DIR
from core.universe import STOCK_DIR, last_member_dates, load_membership
from core.data import bars_path

INTRADAY_DIR = DATA_DIR / "intraday"
START = datetime(2016, 12, 1, tzinfo=timezone.utc)


SAMPLE_SIZE, SAMPLE_SEED = 300, 0


def sample_tickers(n: int = SAMPLE_SIZE, seed: int = SAMPLE_SEED) -> list[str]:
    """The fixed random sample of the member tickers that round 9 uses (sorted)."""
    import numpy as np
    names = sorted(last_member_dates(load_membership()))
    pick = np.random.default_rng(seed).choice(len(names), size=min(n, len(names)), replace=False)
    return sorted(names[i] for i in pick)


def intraday_path(symbol: str):
    return INTRADAY_DIR / f"{symbol.upper()}.csv"


def snapshots(bars: pd.DataFrame) -> pd.DataFrame:
    """bars: 15-minute bars indexed by New York timestamp -> one row per session."""
    t = bars.index
    minutes = t.hour * 60 + t.minute
    day = pd.Series(t.date, index=t)
    out = pd.DataFrame({
        "p1530": bars["close"][minutes == 15 * 60 + 15].groupby(day[minutes == 15 * 60 + 15].values).last(),
        "p1545": bars["close"][minutes == 15 * 60 + 30].groupby(day[minutes == 15 * 60 + 30].values).last(),
        "vol1545": bars["volume"][(minutes >= 9 * 60 + 30) & (minutes <= 15 * 60 + 30)]
        .groupby(day[(minutes >= 9 * 60 + 30) & (minutes <= 15 * 60 + 30)].values).sum(),
    })
    out.index.name = "date"
    return out


def fetch_one(client, symbol: str, asof: str, end: datetime, tries: int = 6) -> int:
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
    from alpaca.data.enums import Adjustment
    request = StockBarsRequest(symbol_or_symbols=symbol.upper(), timeframe=TimeFrame(15, TimeFrameUnit.Minute),
                               start=START, end=end, adjustment=Adjustment.ALL, asof=asof)
    for attempt in range(tries):
        try:
            df = client.get_stock_bars(request).df
            break
        except Exception as exc:
            if attempt == tries - 1:
                raise
            time.sleep(2 ** attempt + 1)
    if df.empty:
        raise ValueError("no bars")
    if isinstance(df.index, pd.MultiIndex):
        df = df.xs(symbol.upper(), level="symbol")
    df.index = pd.to_datetime(df.index).tz_convert("America/New_York")
    out = snapshots(df)
    INTRADAY_DIR.mkdir(parents=True, exist_ok=True)
    out.to_csv(intraday_path(symbol))
    return len(out)


def download(workers: int = 4) -> dict:
    keys = load_paper_keys()
    from alpaca.data.historical import StockHistoricalDataClient
    client = StockHistoricalDataClient(keys.api_key, keys.secret_key)
    end = datetime.now(timezone.utc) - timedelta(minutes=20)
    manifest_path = INTRADAY_DIR / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {"done": {}, "missing": {}}
    chosen = set(sample_tickers())
    todo = [(t, str(a.date())) for t, a in last_member_dates(load_membership()).items()
            if t in chosen and bars_path(t, STOCK_DIR).exists() and not intraday_path(t).exists()]
    print(f"{len(todo)} tickers to fetch", flush=True)
    with ThreadPoolExecutor(workers) as pool:
        futures = {pool.submit(fetch_one, client, t, a, end): t for t, a in todo}
        for n, future in enumerate(as_completed(futures), 1):
            ticker = futures[future]
            try:
                manifest["done"][ticker] = future.result()
            except Exception as exc:
                manifest["missing"][ticker] = f"{type(exc).__name__}: {exc}"[:200]
            if n % 25 == 0:
                print(f"{n}/{len(todo)}", flush=True)
                manifest_path.write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    manifest_path.write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    return manifest


def load_snapshots(tickers, field: str) -> pd.DataFrame:
    frames = {}
    for t in tickers:
        path = intraday_path(t)
        if path.exists():
            frames[t] = pd.read_csv(path, index_col="date", parse_dates=True)[field]
    return pd.DataFrame(frames).sort_index()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("action", choices=["download"])
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    manifest = download(args.workers)
    print(f"{len(manifest['done'])} tickers done, {len(manifest['missing'])} missing")


if __name__ == "__main__":
    main()
