"""Download daily bars from Alpaca into data/ and load them back.

Prices are adjusted for splits and dividends, and only completed sessions are saved (a bar for a
session still in progress is dropped). Downloading needs your paper keys; loading cached files
does not.

    python -m core.data SPY QQQ --start 2016-01-01
"""

import argparse
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

import pandas as pd
from alpaca.data.enums import Adjustment
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

from core.config import ROOT, PaperKeys, load_paper_keys

DATA_DIR = ROOT / "data"
COLUMNS = ["open", "high", "low", "close", "volume"]


def bars_path(symbol: str, data_dir: Path = DATA_DIR) -> Path:
    return data_dir / f"{symbol.upper()}_1Day.csv"


def drop_incomplete_session(df: pd.DataFrame, end: datetime) -> pd.DataFrame:
    """Drop a bar dated D unless the 16:00 New York close of D had passed by `end`.

    A request made during the session returns today's bar as it stands so far, with partial
    volume and a close that is only the latest trade; saving it would pass it off as a full day.
    """
    end_ny = pd.Timestamp(end)
    end_ny = (end_ny.tz_localize("UTC") if end_ny.tzinfo is None else end_ny).tz_convert("America/New_York")
    last_complete = end_ny.date() if end_ny.time() >= time(16, 0) else end_ny.date() - timedelta(days=1)
    return df[df.index <= last_complete]


def download_daily_bars(symbol: str, start: datetime, end: datetime | None = None, *,
                        keys: PaperKeys | None = None, client=None,
                        data_dir: Path = DATA_DIR, asof: str | None = None) -> Path:
    """asof (YYYY-MM-DD) names the date on which `symbol` was the ticker: Alpaca then returns that
    company's whole history across later renames (FB as of 2022-06-01 gives the META bars)."""
    if client is None:
        keys = keys or load_paper_keys()
        client = StockHistoricalDataClient(keys.api_key, keys.secret_key)
    # The free data plan rejects the most recent 15 minutes of consolidated data.
    end = end or datetime.now(timezone.utc) - timedelta(minutes=20)
    extra = {"asof": asof} if asof else {}
    request = StockBarsRequest(symbol_or_symbols=symbol.upper(), timeframe=TimeFrame.Day,
                               start=start, end=end, adjustment=Adjustment.ALL, **extra)
    df = client.get_stock_bars(request).df
    if df.empty:
        raise ValueError(f"no bars returned for {symbol}")
    if isinstance(df.index, pd.MultiIndex):
        df = df.xs(symbol.upper(), level="symbol")
    df.index = pd.to_datetime(df.index).tz_convert("America/New_York").date
    df.index.name = "date"
    df = drop_incomplete_session(df, end)
    if df.empty:
        raise ValueError(f"no completed sessions returned for {symbol}")
    data_dir.mkdir(parents=True, exist_ok=True)
    path = bars_path(symbol, data_dir)
    df[COLUMNS].to_csv(path)
    return path


def load_bars(symbol: str, data_dir: Path = DATA_DIR) -> pd.DataFrame:
    path = bars_path(symbol, data_dir)
    if not path.exists():
        raise FileNotFoundError(f"{path} not found; run: python -m core.data {symbol.upper()}")
    return pd.read_csv(path, index_col="date", parse_dates=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Download daily bars from Alpaca into data/")
    parser.add_argument("symbols", nargs="+")
    parser.add_argument("--start", default="2016-01-01", help="YYYY-MM-DD")
    args = parser.parse_args()
    start = datetime.fromisoformat(args.start).replace(tzinfo=timezone.utc)
    keys = load_paper_keys()
    for symbol in args.symbols:
        path = download_daily_bars(symbol, start, keys=keys)
        print(f"{symbol.upper()}: {len(pd.read_csv(path))} bars -> {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
