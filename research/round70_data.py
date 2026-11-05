"""Data for round 70 (research/r70-10k-text-2026-11-05.md): readability and tone of the MD&A of each 10-K of a current S&P 500 member.

    SEC_CONTACT="..." PYTHONPATH=. python research/round70_data.py [--limit N]    # data/round70/filings/<SYMBOL>.csv, then data/round70/text.csv

data/round70/lm.csv holds the Loughran-McDonald word list (Negative flag and syllable counts) taken from the pysentiment2 package; it is
git-ignored. For each original 10-K filed from 2015-10 on, the Item 7 (MD&A) text is cut out of the filing (tags removed, tables removed first and kept only if that leaves under 1,000 words; the longest
span between an 'Item 7 ... Management's Discussion' heading and the next 'Item 7A' / 'Item 8' heading, which skips table-of-contents lines) and
scored: Gunning Fog index (0.4 x (words per sentence + 100 x share of words with three or more syllables)) and the share of words that are
Loughran-McDonald negative. Raw filings are not kept. Resumable by symbol.
"""

import argparse
import html
import json
import multiprocessing as mp
import os
import re
import time
import urllib.request

import pandas as pd

from core.config import ROOT
from core.edgar import SUBMISSIONS_URL, load_constituents

OUT = ROOT / "data" / "round70"
ARCHIVE = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{doc}"
EARLIEST = "2015-10-01"
PROCESSES, PAUSE = 5, 0.65
START = re.compile(r"item\s*7\s*\.?[\s\-:–— ]{0,8}management[’'`s ]{1,4}s?\s*discussion", re.I)
END = re.compile(r"item\s*7a\b|item\s*8\s*\.?[\s\-:–— ]{0,8}(consolidated\s+)?financial\s+statements", re.I)
_LM = None


def lm():
    global _LM
    if _LM is None:
        d = pd.read_csv(OUT / "lm.csv", keep_default_na=False)
        _LM = ({w: int(s) for w, s in zip(d["Word"], d["Syllables"])}, set(d.loc[d["Negative"] > 0, "Word"]))
    return _LM


def fetch(url, retries=4):
    headers = {"User-Agent": os.environ["SEC_CONTACT"], "Accept-Encoding": "identity"}
    for k in range(retries):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=90).read()
        except Exception:
            if k == retries - 1:
                raise
            time.sleep(2 ** k)


def plain(raw, tables=False):
    s = raw.decode("utf-8", "ignore")
    s = re.sub(r"(?is)<ix:header>.*?</ix:header>", " ", s)
    s = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", s)
    if not tables:
        s = re.sub(r"(?is)<table\b.*?</table>", " ", s)
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html.unescape(s))


def mdna(text):
    best = ""
    for m in START.finditer(text):
        e = END.search(text, m.end())
        span = text[m.end(): e.start() if e else m.end() + 400000]
        if len(span) > len(best):
            best = span
    return best[:600000]


def syllables(word, table):
    if word in table:
        return table[word]
    return max(1, len(re.findall(r"[aeiouy]+", word)) - (1 if word.endswith("e") and len(word) > 3 else 0))


def score(text):
    syl, neg = lm()
    words = re.findall(r"[a-z]{2,}", text.lower())
    n = len(words)
    sentences = max(1, len(re.findall(r"[.!?](?:\s|$)", text)))
    if n < 1000:
        return {"words": n, "fog": float("nan"), "neg": float("nan")}
    complex_ = sum(syllables(w, syl) >= 3 for w in words)
    return {"words": n, "fog": 0.4 * (n / sentences + 100 * complex_ / n), "neg": sum(w in neg for w in words) / n}


def list_filings(cik):
    payload = json.loads(fetch(SUBMISSIONS_URL.format(name=f"CIK{cik:010d}.json")))
    rows = []
    blocks = [payload["filings"]["recent"]]
    for page in payload["filings"].get("files", []):
        if page.get("filingTo", "9999") >= EARLIEST:
            time.sleep(PAUSE)
            blocks.append(json.loads(fetch(SUBMISSIONS_URL.format(name=page["name"]))))
    for b in blocks:
        for k, form in enumerate(b["form"]):
            if form == "10-K" and b["filingDate"][k] >= EARLIEST:
                rows.append({"accession": b["accessionNumber"][k], "filed": b["filingDate"][k], "report_date": b["reportDate"][k], "doc": b["primaryDocument"][k]})
    return sorted(rows, key=lambda r: r["filed"])


def process_company(job):
    symbol, cik = job
    path = OUT / "filings" / f"{symbol}.csv"
    if path.exists():
        return symbol, "cached"
    try:
        out = []
        for r in list_filings(cik):
            time.sleep(PAUSE)
            try:
                raw = fetch(ARCHIVE.format(cik=cik, acc=r["accession"].replace("-", ""), doc=r["doc"]))
                res = score(mdna(plain(raw)))
                if res["words"] < 1000:
                    res = score(mdna(plain(raw, tables=True)))
                out.append({**r, "symbol": symbol, **res, "error": ""})
            except Exception as exc:
                out.append({**r, "symbol": symbol, "error": type(exc).__name__})
        pd.DataFrame(out).to_csv(path, index=False)
        return symbol, f"{len(out)} filings"
    except Exception as exc:
        return symbol, f"FAILED {type(exc).__name__}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()
    (OUT / "filings").mkdir(parents=True, exist_ok=True)
    jobs = sorted(load_constituents().items())
    if args.limit:
        jobs = jobs[: args.limit]
    with mp.Pool(PROCESSES) as pool:
        for n, r in enumerate(pool.imap_unordered(process_company, jobs), 1):
            print(n, r, flush=True)
    frames = [pd.read_csv(p) for p in sorted((OUT / "filings").glob("*.csv")) if p.stat().st_size > 5]
    pd.concat(frames, ignore_index=True).to_csv(OUT / "text.csv", index=False)
    print("done")


def load_text() -> pd.DataFrame:
    return pd.read_csv(OUT / "text.csv", parse_dates=["filed", "report_date"])


if __name__ == "__main__":
    main()
