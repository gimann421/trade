"""Data for round 63 (research/r63-rpo-comment-letters-smoothing-2026-11-02.md).

    PYTHONPATH=. python research/round63_data.py facts     # data/round63/facts.csv  (RPO and revenue companyconcept tags)
    PYTHONPATH=. python research/round63_data.py letters   # data/round63/letters.csv (SEC staff UPLOAD filings, 2014-01 on)
"""

import sys
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

from core.data import DATA_DIR
from core.edgar import load_constituents
from research import round25_data, round44_data

OUT = DATA_DIR / "round63"
TAGS = ("RevenueRemainingPerformanceObligation", "RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues")
START = "2014-01-01"


def fetch_facts() -> pd.DataFrame:
    return round25_data.fetch(tags=TAGS, out=OUT)


def _letters(job):
    symbol, cik = job
    top = round44_data._get(f"CIK{cik:010d}.json")
    if top is None:
        return symbol, None
    blocks = [top["filings"]["recent"]]
    if min(top["filings"]["recent"]["filingDate"]) > START:
        for f in top["filings"]["files"]:
            if f["filingTo"] >= START:
                extra = round44_data._get(f["name"])
                if extra is not None:
                    blocks.append(extra)
    rows = [(symbol, d, f) for b in blocks for d, f in zip(b["filingDate"], b["form"]) if f == "UPLOAD" and d >= START]
    reach = min(min(b["filingDate"]) for b in blocks)
    return symbol, (rows, reach)


def fetch_letters(workers: int = 3) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    jobs = sorted(load_constituents().items())
    rows, reach, failed = [], {}, []
    with ThreadPoolExecutor(workers) as pool:
        for n, (symbol, res) in enumerate(pool.map(_letters, jobs), 1):
            if res is None:
                failed.append(symbol)
            else:
                rows.extend(res[0])
                reach[symbol] = res[1]
            if n % 50 == 0:
                print(n, len(rows), "failed", failed, flush=True)
    pd.DataFrame(rows, columns=["symbol", "filed", "form"]).to_csv(OUT / "letters.csv", index=False)
    pd.Series(reach, name="history_from").to_csv(OUT / "reach.csv")
    print("done; failed:", failed)


def load_facts() -> pd.DataFrame:
    return pd.read_csv(OUT / "facts.csv", parse_dates=["start", "end", "filed"])


def load_letters() -> pd.DataFrame:
    return pd.read_csv(OUT / "letters.csv", parse_dates=["filed"])


def load_reach() -> pd.Series:
    return pd.read_csv(OUT / "reach.csv", index_col=0).iloc[:, 0].map(pd.Timestamp)


if __name__ == "__main__":
    {"facts": fetch_facts, "letters": fetch_letters}[sys.argv[1]]()
