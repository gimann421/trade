"""Download 10-K and 10-Q text for the current S&P 500 members and score each filing against the year-earlier one.

    SEC_CONTACT="trade-research you@example.com" PYTHONPATH=. python research/round16_filings_data.py [--limit N]

The SEC refuses requests whose user agent has no contact address, so the contact comes from the environment and is never stored.
Output (git-ignored): data/round16/filings/<SYMBOL>.csv with one row per filing: accepted time, report date, cosine and Jaccard
similarity to the same form's filing about a year earlier, word count. Raw filings are not kept. Resumable by symbol.
"""

import argparse
import csv
import html
import io
import json
import multiprocessing as mp
import os
import re
import time
import urllib.request
from collections import Counter
from datetime import date

import numpy as np
import pandas as pd

from core.config import ROOT
from core.edgar import SUBMISSIONS_URL, load_constituents

OUT = ROOT / "data" / "round16" / "filings"
ARCHIVE = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{doc}"
EARLIEST = "2015-01-01"
FORMS = ("10-K", "10-Q")
PROCESSES, PAUSE = 5, 0.65          # about 7.7 requests a second in all, under the SEC's limit of 10
MIN_WORDS = 3000
PRIOR_DAYS, PRIOR_TOL = 365, 45


def fetch(url: str, retries: int = 4) -> bytes:
    headers = {"User-Agent": os.environ["SEC_CONTACT"], "Accept-Encoding": "identity"}
    for k in range(retries):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=90).read()
        except Exception:
            if k == retries - 1:
                raise
            time.sleep(2 ** k)


def filing_rows(block: dict) -> list[dict]:
    rows = []
    for k, form in enumerate(block["form"]):
        if form in FORMS and block["filingDate"][k] >= EARLIEST:
            rows.append({"form": form, "accession": block["accessionNumber"][k], "filing_date": block["filingDate"][k],
                         "accepted": block["acceptanceDateTime"][k], "report_date": block["reportDate"][k],
                         "doc": block["primaryDocument"][k]})
    return rows


def list_filings(cik: int) -> list[dict]:
    payload = json.loads(fetch(SUBMISSIONS_URL.format(name=f"CIK{cik:010d}.json")))
    rows = filing_rows(payload["filings"]["recent"])
    for page in payload["filings"].get("files", []):
        if page.get("filingTo", "9999") >= EARLIEST:
            time.sleep(PAUSE)
            rows += filing_rows(json.loads(fetch(SUBMISSIONS_URL.format(name=page["name"]))))
    return sorted(rows, key=lambda r: r["accepted"])


def word_counts(raw: bytes) -> Counter:
    s = raw.decode("utf-8", "ignore")
    s = re.sub(r"(?is)<ix:header>.*?</ix:header>", " ", s)
    s = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", s)
    s = re.sub(r"(?is)<table\b.*?</table>", " ", s)
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    return Counter(re.findall(r"[a-z]{2,}", html.unescape(s).lower()))


def cosine(a: Counter, b: Counter) -> float:
    small, big = (a, b) if len(a) < len(b) else (b, a)
    dot = sum(v * big.get(k, 0) for k, v in small.items())
    return dot / (np.sqrt(sum(v * v for v in a.values())) * np.sqrt(sum(v * v for v in b.values())))


def jaccard(a: Counter, b: Counter) -> float:
    ka, kb = set(a), set(b)
    return len(ka & kb) / len(ka | kb)


def prior_match(history: list, report_date: str):
    """The earlier filing of the same form whose report date is about one year before `report_date`."""
    target = pd.Timestamp(report_date) - pd.Timedelta(days=PRIOR_DAYS)
    best = None
    for rd, acc, words in history:
        gap = abs((pd.Timestamp(rd) - target).days)
        if gap <= PRIOR_TOL and (best is None or gap < best[0]):
            best = (gap, acc, words)
    return best


def process_company(job):
    symbol, cik = job
    path = OUT / f"{symbol}.csv"
    if path.exists():
        return symbol, "cached"
    try:
        rows = list_filings(cik)
        history = {form: [] for form in FORMS}
        out = []
        for r in rows:
            time.sleep(PAUSE)
            try:
                words = word_counts(fetch(ARCHIVE.format(cik=cik, acc=r["accession"].replace("-", ""), doc=r["doc"])))
            except Exception as exc:
                out.append({**r, "symbol": symbol, "error": f"{type(exc).__name__}"[:40]})
                continue
            n = sum(words.values())
            row = {**r, "symbol": symbol, "words": n, "error": "" if n >= MIN_WORDS else "short"}
            if n >= MIN_WORDS and r["report_date"]:
                match = prior_match(history[r["form"]], r["report_date"])
                if match:
                    row |= {"prior_accession": match[1], "cosine": cosine(words, match[2]), "jaccard": jaccard(words, match[2])}
                history[r["form"]].append((r["report_date"], r["accession"], words))
                history[r["form"]] = history[r["form"]][-6:]
            out.append(row)
        OUT.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(out).to_csv(path, index=False)
        return symbol, f"{len(out)} filings"
    except Exception as exc:
        return symbol, f"FAILED {type(exc).__name__}: {str(exc)[:80]}"


def load_scores() -> pd.DataFrame:
    frames = [pd.read_csv(p) for p in sorted(OUT.glob("*.csv"))]
    frame = pd.concat(frames, ignore_index=True)
    frame["accepted"] = pd.to_datetime(frame["accepted"], utc=True)
    return frame


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--limit", type=int, default=0, help="only the first N symbols (for a speed check)")
    args = parser.parse_args()
    jobs = sorted(load_constituents().items())
    if args.limit:
        jobs = jobs[:args.limit]
    OUT.mkdir(parents=True, exist_ok=True)
    start, done = time.time(), 0
    with mp.Pool(PROCESSES) as pool:
        for symbol, status in pool.imap_unordered(process_company, jobs):
            done += 1
            print(f"{done}/{len(jobs)} {symbol}: {status}  ({time.time() - start:.0f}s)", flush=True)


if __name__ == "__main__":
    main()
