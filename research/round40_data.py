"""Data for round 40 (research/r40-affiliate-ownership-2026-10-29.md): cover-page public float from SEC XBRL (dei EntityPublicFloat, USD).

    PYTHONPATH=. python research/round40_data.py       # data/round40/facts.csv
"""

import json
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

from core.data import DATA_DIR
from core.edgar import HEADERS, load_constituents

OUT = DATA_DIR / "round40"
URL = "https://data.sec.gov/api/xbrl/companyconcept/CIK{cik:010d}/dei/EntityPublicFloat.json"


def _one(symbol, cik):
    for attempt in range(3):
        try:
            payload = json.loads(urllib.request.urlopen(urllib.request.Request(URL.format(cik=cik), headers=HEADERS), timeout=60).read())
            return [{"symbol": symbol, "end": r["end"], "val": r["val"], "form": r.get("form"), "filed": r["filed"]} for r in payload["units"].get("USD", [])]
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None
            time.sleep(1 + attempt)
        except Exception:
            time.sleep(1 + attempt)
    return None


def fetch(workers: int = 6) -> pd.DataFrame:
    OUT.mkdir(parents=True, exist_ok=True)
    jobs = sorted(load_constituents().items())
    rows = []
    with ThreadPoolExecutor(workers) as pool:
        for result in pool.map(lambda j: _one(*j), jobs):
            rows.extend(result or [])
    frame = pd.DataFrame(rows)
    frame.to_csv(OUT / "facts.csv", index=False)
    print(frame.symbol.nunique(), "of", len(jobs))
    return frame


def load_facts() -> pd.DataFrame:
    return pd.read_csv(OUT / "facts.csv", parse_dates=["end", "filed"])


if __name__ == "__main__":
    fetch()
