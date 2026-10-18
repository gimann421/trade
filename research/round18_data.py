"""Data for round 18 (research/r18-ranked-ideas-2026-10-18.md): quarterly diluted EPS from SEC XBRL for the current S&P 500.

    PYTHONPATH=. python research/round18_data.py eps     # data/round18/eps.csv
    python -m core.industry                               # data/edgar/sic.csv (industry codes)
    python -m core.edgar                                  # data/edgar/events.csv (8-K Item 2.02 earnings releases)

EPS comes from data.sec.gov companyconcept us-gaap/EarningsPerShareDiluted (EarningsPerShareBasic when a company reports
no diluted figure). Every fact keeps its period (start, end), the form and the date it was filed, so a value is usable only
from its filing date on.
"""

import json
import sys
import time
import urllib.request

import pandas as pd

from core.data import DATA_DIR
from core.edgar import HEADERS, load_constituents

OUT = DATA_DIR / "round18"
CONCEPT = "https://data.sec.gov/api/xbrl/companyconcept/CIK{cik:010d}/us-gaap/{tag}.json"


def fetch_eps() -> pd.DataFrame:
    OUT.mkdir(parents=True, exist_ok=True)
    rows, missing = [], []
    for n, (symbol, cik) in enumerate(sorted(load_constituents().items()), 1):
        got = False
        for tag in ("EarningsPerShareDiluted", "EarningsPerShareBasic"):
            try:
                req = urllib.request.Request(CONCEPT.format(cik=cik, tag=tag), headers=HEADERS)
                payload = json.loads(urllib.request.urlopen(req, timeout=60).read())
            except Exception:
                time.sleep(0.12)
                continue
            for unit, facts in payload["units"].items():
                for r in facts:
                    rows.append({"symbol": symbol, "cik": cik, "tag": tag, "unit": unit, "start": r.get("start"), "end": r["end"],
                                 "val": r["val"], "fy": r.get("fy"), "fp": r.get("fp"), "form": r.get("form"), "filed": r["filed"]})
            got = True
            time.sleep(0.12)
            break
        if not got:
            missing.append(symbol)
        if n % 100 == 0:
            print(n, len(rows), len(missing), flush=True)
    frame = pd.DataFrame(rows)
    frame.to_csv(OUT / "eps.csv", index=False)
    (OUT / "eps_missing.json").write_text(json.dumps(missing, indent=1))
    print(f"{frame.symbol.nunique()} symbols with EPS, {len(missing)} without")
    return frame


def load_eps() -> pd.DataFrame:
    return pd.read_csv(OUT / "eps.csv", parse_dates=["start", "end", "filed"])


if __name__ == "__main__":
    if sys.argv[1:] == ["eps"]:
        fetch_eps()
    else:
        print(__doc__)
