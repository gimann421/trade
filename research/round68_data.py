"""Data for round 68 (research/r68-lobbying-2026-11-05.md): Senate lobbying disclosure filings (lda.gov API, no key) for current members.

    PYTHONPATH=. python research/round68_data.py     # data/round68/filings.csv

Per member and filing year 2016-2026: all filings whose client name contains the member's SEC name, kept only when the normalised client name
equals the normalised SEC name or a former name (no hand matching). Rows: member, client, registrant, year, quarter, income, expenses, date posted.
"""

import json
import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

from core.data import DATA_DIR
from core.edgar import load_constituents
from research import round44_data

OUT = DATA_DIR / "round68"
URL = "https://lda.gov/api/v1/filings/?client_name={q}&filing_year={y}&page_size=25"
UA = {"User-Agent": "trade-research personal-research-script", "Accept": "application/json"}
SUFFIX = re.compile(r"\b(INC|INCORPORATED|CORP|CORPORATION|CO|COMPANY|LTD|LIMITED|PLC|LLC|LP|NV|SA|AG|THE|DE)\b")
TYPES = {"Q1", "Q2", "Q3", "Q4", "Q1A", "Q2A", "Q3A", "Q4A"}


def norm(name):
    s = re.sub(r"[^A-Z0-9 ]", " ", str(name).upper().replace("&", " AND "))
    return re.sub(r"\s+", " ", SUFFIX.sub(" ", s)).strip()


def _page(url):
    for attempt in range(5):
        try:
            return json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=90).read())
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None
            time.sleep(3 + 3 * attempt)
        except Exception:
            time.sleep(3 + 3 * attempt)
    return None


def _one(job):
    symbol, names = job
    keys = {norm(n) for n in names}
    query = urllib.request.quote(sorted(names, key=len)[0] if False else job[1][0])
    rows = []
    for year in range(2016, pd.Timestamp.now().year + 1):
        url = URL.format(q=query, y=year)
        while url:
            d = _page(url)
            if d is None:
                break
            for r in d["results"]:
                if r["filing_type"] in TYPES and norm(r["client"]["name"]) in keys:
                    rows.append((symbol, r["client"]["name"], r["registrant"]["name"], r["registrant"]["id"], r["filing_year"], r["filing_period"], r["filing_type"],
                                 r["income"], r["expenses"], r["dt_posted"]))
            url = d.get("next")
    return symbol, rows


def fetch(workers=10):
    OUT.mkdir(parents=True, exist_ok=True)
    jobs = []
    for symbol, cik in sorted(load_constituents().items()):
        top = round44_data._get(f"CIK{cik:010d}.json")
        if top:
            jobs.append((symbol, [top["name"]] + [f["name"] for f in top.get("formerNames", [])[:3]]))
    rows = []
    with ThreadPoolExecutor(workers) as pool:
        for n, (symbol, r) in enumerate(pool.map(_one, jobs), 1):
            rows.extend(r)
            if n % 10 == 0:
                print(n, len(rows), flush=True)
    cols = ["symbol", "client", "registrant", "registrant_id", "year", "period", "type", "income", "expenses", "posted"]
    pd.DataFrame(rows, columns=cols).to_csv(OUT / "filings.csv", index=False)
    print("done", len(rows))


def load_filings() -> pd.DataFrame:
    f = pd.read_csv(OUT / "filings.csv")
    f["posted"] = pd.to_datetime(f["posted"], utc=True, format="ISO8601").dt.tz_localize(None).dt.normalize()
    return f


if __name__ == "__main__":
    sys.exit(fetch())
