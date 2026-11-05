"""Data for round 67 (research/r67-short-interest-2026-11-05.md): FINRA consolidated short interest per current S&P 500 member.

    PYTHONPATH=. python research/round67_data.py     # data/round67/shortint.csv

One request per symbol (api.finra.org, no key), settlement dates from 2018-06 on: settlement date, current short position, previous position.
Members whose symbol FINRA does not know (share classes with a dot or dash) are listed and left out.
"""

import json
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

from core.data import DATA_DIR
from core.edgar import load_constituents

OUT = DATA_DIR / "round67"
URL = "https://api.finra.org/data/group/otcMarket/name/consolidatedShortInterest"


def _one(symbol):
    body = {"limit": 5000, "fields": ["symbolCode", "settlementDate", "currentShortPositionQuantity", "revisionFlag"],
            "compareFilters": [{"compareType": "EQUAL", "fieldName": "symbolCode", "fieldValue": symbol},
                               {"compareType": "GREATER", "fieldName": "settlementDate", "fieldValue": "2018-06-01"}]}
    for attempt in range(4):
        try:
            req = urllib.request.Request(URL, data=json.dumps(body).encode(), headers={"Content-Type": "application/json", "Accept": "application/json"})
            raw = urllib.request.urlopen(req, timeout=60).read()
            return symbol, json.loads(raw) if raw.strip() else []
        except urllib.error.HTTPError as exc:
            if exc.code in (400, 404):
                return symbol, None
            time.sleep(2 + 2 * attempt)
        except Exception:
            time.sleep(2 + 2 * attempt)
    return symbol, None


def fetch(workers=4):
    OUT.mkdir(parents=True, exist_ok=True)
    symbols = sorted(load_constituents())
    rows, miss = [], []
    with ThreadPoolExecutor(workers) as pool:
        for n, (symbol, res) in enumerate(pool.map(_one, symbols), 1):
            if not res:
                miss.append(symbol)
            else:
                rows.extend(res)
            if n % 100 == 0:
                print(n, len(rows), "missing", len(miss), flush=True)
    frame = pd.DataFrame(rows)
    frame.to_csv(OUT / "shortint.csv", index=False)
    print("rows", len(frame), "symbols", frame["symbolCode"].nunique(), "missing", miss)


def load_shortint() -> pd.DataFrame:
    f = pd.read_csv(OUT / "shortint.csv", parse_dates=["settlementDate"])
    return f.rename(columns={"symbolCode": "symbol", "settlementDate": "settle", "currentShortPositionQuantity": "short"})


if __name__ == "__main__":
    sys.exit(fetch())
