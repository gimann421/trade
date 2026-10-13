"""Point-in-time S&P 500 membership and the member price files.

Membership comes from fja05680/sp500 on GitHub ("S&P 500 Historical Components & Changes
(Updated).csv"): one row per change date, listing every member's ticker as it was that day.
Members on a date are the row dated on or before it. Tickers are the names in use at the time,
so each one is downloaded with Alpaca's `asof` set to the last day it was a member under that
name; the bars then follow the same company across later renames.

    python -m core.universe fetch            # membership file -> data/sp500_members.csv
    python -m core.universe download         # member bars -> data/sp500/
"""

import argparse
import hashlib
import json
import time
import urllib.request
from datetime import datetime, timezone

import pandas as pd

from core.config import ROOT, load_paper_keys
from core.data import DATA_DIR, bars_path, download_daily_bars, load_bars

MEMBERS_URL = ("https://raw.githubusercontent.com/fja05680/sp500/master/"
               "S%26P%20500%20Historical%20Components%20%26%20Changes%20(Updated).csv")
MEMBERS_PATH = DATA_DIR / "sp500_members.csv"
STOCK_DIR = DATA_DIR / "sp500"
MANIFEST_PATH = STOCK_DIR / "manifest.json"
# months whose month-end membership the strategy can use
FIRST_MONTH_END, LAST_MONTH_END = "2016-12-31", "2026-12-31"


def fetch_membership(url: str = MEMBERS_URL) -> dict:
    """Download the membership file; returns its sha256, row count and last date."""
    with urllib.request.urlopen(url, timeout=60) as response:
        body = response.read()
    MEMBERS_PATH.parent.mkdir(parents=True, exist_ok=True)
    MEMBERS_PATH.write_bytes(body)
    table = load_membership()
    return {"url": url, "sha256": hashlib.sha256(body).hexdigest(), "rows": len(table),
            "first": str(table.index[0].date()), "last": str(table.index[-1].date())}


def load_membership(path=MEMBERS_PATH) -> pd.Series:
    """Series of frozensets of tickers, indexed by change date."""
    raw = pd.read_csv(path, parse_dates=["date"]).set_index("date").sort_index()
    return raw["tickers"].map(lambda s: frozenset(t.strip() for t in s.split(",") if t.strip()))


def members_on(membership: pd.Series, dates) -> list[frozenset]:
    """Members as of each date (the latest row dated on or before it)."""
    positions = membership.index.searchsorted(pd.DatetimeIndex(dates), side="right") - 1
    if (positions < 0).any():
        raise ValueError("a date precedes the membership history")
    return [membership.iloc[p] for p in positions]


def month_end_members(membership: pd.Series, start=FIRST_MONTH_END, end=LAST_MONTH_END) -> set:
    """Every ticker that is a member at some calendar month-end in [start, end]."""
    month_ends = pd.date_range(start, end, freq="ME")
    return set().union(*members_on(membership, month_ends))


def last_member_dates(membership: pd.Series, start=FIRST_MONTH_END, end=LAST_MONTH_END) -> dict:
    """For each ticker in month_end_members, the last membership row (change date) listing it:
    a day on which the ticker named the company we want."""
    wanted = month_end_members(membership, start, end)
    last = {}
    for when, members in membership.loc[:pd.Timestamp(end)].items():
        for ticker in members & wanted:
            last[ticker] = when
    return dict(sorted(last.items()))


def download_members(start=datetime(2016, 1, 1, tzinfo=timezone.utc), pause: float = 0.35,
                     refresh: bool = False) -> dict:
    """Download bars for every ticker in last_member_dates; skips files already present unless
    refresh. Writes a manifest with the asof date used and any ticker Alpaca had no bars for."""
    keys = load_paper_keys()
    from alpaca.data.historical import StockHistoricalDataClient
    client = StockHistoricalDataClient(keys.api_key, keys.secret_key)
    STOCK_DIR.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(MANIFEST_PATH.read_text()) if MANIFEST_PATH.exists() else {"asof": {}, "missing": {}}
    for ticker, asof in last_member_dates(load_membership()).items():
        asof = str(asof.date())
        if not refresh and bars_path(ticker, STOCK_DIR).exists() and manifest["asof"].get(ticker) == asof:
            continue
        try:
            download_daily_bars(ticker, start, client=client, data_dir=STOCK_DIR, asof=asof)
            manifest["asof"][ticker] = asof
            manifest["missing"].pop(ticker, None)
        except Exception as exc:  # no bars, unknown symbol
            manifest["missing"][ticker] = f"{type(exc).__name__}: {exc}"[:200]
        time.sleep(pause)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    return manifest


def load_member_closes(tickers) -> pd.DataFrame:
    """Close prices (split- and dividend-adjusted) for the tickers that have a file, one column each."""
    closes = {t: load_bars(t, STOCK_DIR)["close"] for t in tickers if bars_path(t, STOCK_DIR).exists()}
    return pd.DataFrame(closes).sort_index()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("action", choices=["fetch", "download"])
    args = parser.parse_args()
    if args.action == "fetch":
        print(json.dumps(fetch_membership(), indent=1))
    else:
        manifest = download_members()
        print(f"{len(manifest['asof'])} tickers with bars, {len(manifest['missing'])} missing "
              f"-> {MANIFEST_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
