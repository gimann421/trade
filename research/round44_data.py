"""Data for round 44 (research/r44-insider-filings-2026-10-29.md): filing history from the SEC submissions API (data.sec.gov).

    PYTHONPATH=. python research/round44_data.py       # data/round44/filings.csv

One row per filing of form 4, 144, 8-K or 10-K/A from 2015-10 on: symbol, filingDate, form, items (8-K item codes). Current S&P 500
members only (the CIK map in core.edgar). Follows the extra history files when the 'recent' block does not reach back to 2015-10.
"""

import json
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

from core.data import DATA_DIR
from core.edgar import HEADERS, load_constituents

OUT = DATA_DIR / "round44"
BASE = "https://data.sec.gov/submissions/"
FORMS = {"4", "144", "8-K", "10-K/A"}
START = "2015-10-01"


def _get(name):
    for attempt in range(5):
        try:
            return json.loads(urllib.request.urlopen(urllib.request.Request(BASE + name, headers=HEADERS), timeout=60).read())
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None
            time.sleep(1 + attempt)
        except Exception:
            time.sleep(1 + attempt)
    return None


def _rows(symbol, block):
    return [(symbol, d, f, i) for d, f, i in zip(block["filingDate"], block["form"], block["items"]) if f in FORMS and d >= START]


def _one(args):
    symbol, cik = args
    top = _get(f"CIK{cik:010d}.json")
    if top is None:
        return symbol, None
    rows = _rows(symbol, top["filings"]["recent"])
    if min(top["filings"]["recent"]["filingDate"]) > START:
        for f in top["filings"]["files"]:
            if f["filingTo"] >= START:
                extra = _get(f["name"])
                if extra is not None:
                    rows.extend(_rows(symbol, extra))
    return symbol, rows


def fetch(workers: int = 3) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    jobs = sorted(load_constituents().items())
    rows, failed = [], []
    with ThreadPoolExecutor(workers) as pool:
        for n, (symbol, result) in enumerate(pool.map(_one, jobs), 1):
            if result is None:
                failed.append(symbol)
            else:
                rows.extend(result)
            if n % 50 == 0:
                print(n, len(rows), "failed", failed, flush=True)
    pd.DataFrame(rows, columns=["symbol", "filed", "form", "items"]).to_csv(OUT / "filings.csv", index=False)
    print("done; failed:", failed)


def load_filings() -> pd.DataFrame:
    return pd.read_csv(OUT / "filings.csv", parse_dates=["filed"], keep_default_na=False)


if __name__ == "__main__":
    fetch()
