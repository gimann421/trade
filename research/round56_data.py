"""Data for round 56 (research/r56-midsmall-replication-2026-10-30.md): current S&P 400 and S&P 600 members, their bars and SEC XBRL facts.

    PYTHONPATH=. python research/round56_data.py constituents   # data/round56/constituents.csv (Wikipedia tables)
    PYTHONPATH=. python research/round56_data.py facts          # data/round56/{r25,r27,r28,shares}/facts.csv
    PYTHONPATH=. python research/round56_data.py bars           # data/round56/bars/ (adjusted) and data/round56/raw/ (unadjusted)

Same tags and loaders as rounds 25, 27, 28 and 36; only the symbol list differs. Current members only, as in every earlier round.
"""

import io
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone

import pandas as pd

from core.data import COLUMNS, DATA_DIR, bars_path, download_daily_bars, drop_incomplete_session, load_paper_keys
from research import round25_data, round27_data, round28_data, round36_data

OUT = DATA_DIR / "round56"
PAGES = {"S&P 400": "https://en.wikipedia.org/wiki/List_of_S%26P_400_companies", "S&P 600": "https://en.wikipedia.org/wiki/List_of_S%26P_600_companies"}


def constituents() -> pd.DataFrame:
    rows = []
    for index, url in PAGES.items():
        html = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "trade-research personal-research-script"}), timeout=60).read().decode()
        table = pd.read_html(io.StringIO(html), extract_links="body")[0]
        for _, r in table.iterrows():
            symbol = r["Symbol"][0].strip()
            cik = None
            if "CIK" in table.columns and r["CIK"][0]:
                cik = int(re.sub(r"\D", "", str(r["CIK"][0])) or 0) or None
            if cik is None and r["SEC filings"][1]:
                m = re.search(r"CIK=0*(\d+)", r["SEC filings"][1])
                cik = int(m.group(1)) if m else None
            if symbol and cik:
                rows.append({"symbol": symbol, "cik": cik, "index": index})
    frame = pd.DataFrame(rows).drop_duplicates("symbol")
    OUT.mkdir(parents=True, exist_ok=True)
    frame.to_csv(OUT / "constituents.csv", index=False)
    print(frame.groupby("index").size().to_dict())
    return frame


def load_constituents_map() -> dict:
    frame = pd.read_csv(OUT / "constituents.csv")
    return dict(zip(frame["symbol"], frame["cik"].astype(int)))


def facts() -> None:
    cmap = load_constituents_map()
    round25_data.load_constituents = lambda: cmap
    round36_data.load_constituents = lambda: cmap
    for name, tags in (("r25", round25_data.TAGS), ("r27", round27_data.TAGS), ("r28", round28_data.TAGS)):
        print("facts", name, flush=True)
        round25_data.fetch(6, tags=tags, out=OUT / name)
    print("shares", flush=True)
    round36_data.OUT = OUT / "shares"
    round36_data.fetch_shares()


def bars() -> None:
    from alpaca.data.enums import Adjustment
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame
    keys = load_paper_keys()
    client = StockHistoricalDataClient(keys.api_key, keys.secret_key)
    symbols = sorted(load_constituents_map())
    start = datetime(2016, 1, 1, tzinfo=timezone.utc)
    end = datetime.now(timezone.utc) - pd.Timedelta(minutes=20)
    (OUT / "bars").mkdir(parents=True, exist_ok=True)
    (OUT / "raw").mkdir(parents=True, exist_ok=True)
    missing = []
    for n, s in enumerate(symbols, 1):
        try:
            if not bars_path(s, OUT / "bars").exists():
                download_daily_bars(s, start, client=client, data_dir=OUT / "bars")
            if not bars_path(s, OUT / "raw").exists():
                df = client.get_stock_bars(StockBarsRequest(symbol_or_symbols=s.upper(), timeframe=TimeFrame.Day, start=start, end=end, adjustment=Adjustment.RAW)).df
                if isinstance(df.index, pd.MultiIndex):
                    df = df.xs(s.upper(), level="symbol")
                df.index = pd.to_datetime(df.index).tz_convert("America/New_York").date
                df.index.name = "date"
                drop_incomplete_session(df, end)[COLUMNS].to_csv(bars_path(s, OUT / "raw"))
        except Exception as exc:
            missing.append((s, str(exc)[:80]))
        if n % 100 == 0:
            print(n, "missing", len(missing), flush=True)
        time.sleep(0.35)
    print("missing", len(missing), missing[:15])


if __name__ == "__main__":
    {"constituents": constituents, "facts": facts, "bars": bars}[sys.argv[1]]()
