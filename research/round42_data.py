"""Data for round 42 (research/r42-news-attention-2026-10-29.md): Alpaca (Benzinga) news headlines per ticker, 2016-10 on.

    PYTHONPATH=. python research/round42_data.py       # data/round42/news.csv.gz  (symbol, created_at, headline)

Every S&P 500 member ticker with stock bars (past and current). Headlines only, no article bodies. Re-run resumes: tickers already in
data/round42/parts/ are skipped.
"""

import time
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import requests

from core.config import load_paper_keys
from core.data import DATA_DIR
from core.universe import STOCK_DIR

OUT = DATA_DIR / "round42"
PARTS = OUT / "parts"
URL = "https://data.alpaca.markets/v1beta1/news"
START, END = "2016-10-01T00:00:00Z", "2026-10-29T00:00:00Z"


def _tickers():
    return sorted(p.name.removesuffix("_1Day.csv") for p in STOCK_DIR.glob("*_1Day.csv"))


def _one(args):
    symbol, headers = args
    path = PARTS / f"{symbol}.csv"
    if path.exists():
        return symbol, -1
    rows, token = [], None
    while True:
        params = {"symbols": symbol, "start": START, "end": END, "limit": 50, "include_content": "false", "sort": "asc"}
        if token:
            params["page_token"] = token
        for attempt in range(8):
            r = requests.get(URL, params=params, headers=headers, timeout=60)
            if r.status_code == 200:
                break
            time.sleep(2 ** attempt)
        else:
            return symbol, None
        j = r.json()
        rows.extend((symbol, a["created_at"], a["headline"]) for a in j.get("news", []))
        token = j.get("next_page_token")
        if not token:
            break
    pd.DataFrame(rows, columns=["symbol", "created_at", "headline"]).to_csv(path, index=False)
    return symbol, len(rows)


def fetch(workers: int = 3) -> None:
    PARTS.mkdir(parents=True, exist_ok=True)
    keys = load_paper_keys()
    headers = {"APCA-API-KEY-ID": keys.api_key, "APCA-API-SECRET-KEY": keys.secret_key}
    failed = []
    with ThreadPoolExecutor(workers) as pool:
        for n, (symbol, count) in enumerate(pool.map(_one, [(s, headers) for s in _tickers()]), 1):
            if count is None:
                failed.append(symbol)
            if n % 25 == 0:
                print(n, "failed", failed, flush=True)
    print("done; failed:", failed)


def load_news() -> pd.DataFrame:
    frames = [pd.read_csv(p) for p in sorted(PARTS.glob("*.csv"))]
    news = pd.concat(frames, ignore_index=True)
    news["created_at"] = pd.to_datetime(news["created_at"], utc=True).dt.tz_convert("America/New_York").dt.tz_localize(None)
    return news


if __name__ == "__main__":
    fetch()
