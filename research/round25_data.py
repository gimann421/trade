"""Data for round 25 (research/r25-quality-2026-10-20.md): annual fundamentals from SEC XBRL for the current S&P 500.

    PYTHONPATH=. python research/round25_data.py       # data/round25/facts.csv

Tags: GrossProfit, Assets, NetIncomeLoss, NetCashProvidedByUsedInOperatingActivities (us-gaap companyconcept). Every fact keeps its period,
form and the date it was filed; a value is usable only from its filing date on. Current members only (the same limit as rounds 16 and 18).
"""

import json
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

from core.data import DATA_DIR
from core.edgar import HEADERS, load_constituents

OUT = DATA_DIR / "round25"
CONCEPT = "https://data.sec.gov/api/xbrl/companyconcept/CIK{cik:010d}/us-gaap/{tag}.json"
TAGS = ("GrossProfit", "Assets", "NetIncomeLoss", "NetCashProvidedByUsedInOperatingActivities")


def _one(symbol: str, cik: int, tag: str):
    for attempt in range(3):
        try:
            req = urllib.request.Request(CONCEPT.format(cik=cik, tag=tag), headers=HEADERS)
            payload = json.loads(urllib.request.urlopen(req, timeout=60).read())
            return [{"symbol": symbol, "cik": cik, "tag": tag, "start": r.get("start"), "end": r["end"], "val": r["val"], "fy": r.get("fy"),
                     "fp": r.get("fp"), "form": r.get("form"), "filed": r["filed"]}
                    for r in payload["units"].get("USD", [])]
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None
            time.sleep(1 + attempt)
        except Exception:
            time.sleep(1 + attempt)
    return None


def fetch(workers: int = 6) -> pd.DataFrame:
    OUT.mkdir(parents=True, exist_ok=True)
    members = sorted(load_constituents().items())
    jobs = [(s, c, t) for s, c in members for t in TAGS]
    rows, missing = [], {t: 0 for t in TAGS}
    with ThreadPoolExecutor(workers) as pool:
        for n, (job, result) in enumerate(zip(jobs, pool.map(lambda j: _one(*j), jobs)), 1):
            if result is None:
                missing[job[2]] += 1
            else:
                rows.extend(result)
            if n % 200 == 0:
                print(n, len(rows), missing, flush=True)
    frame = pd.DataFrame(rows)
    frame.to_csv(OUT / "facts.csv", index=False)
    print(frame.groupby("tag").symbol.nunique().to_dict(), "of", len(members))
    return frame


def load_facts() -> pd.DataFrame:
    return pd.read_csv(OUT / "facts.csv", parse_dates=["start", "end", "filed"])


if __name__ == "__main__":
    fetch()
