"""Data for round 69 (research/r69-segment-focus-2026-11-05.md): business-segment revenue from the SEC Financial Statement Data Sets.

    SEC_CONTACT="..." PYTHONPATH=. python research/round69_data.py     # data/round69/filings.csv

One row per original 10-K of a current member from 2015q4 on: cik, adsh, filed, period, has_total (a non-dimensional revenue fact for the fiscal year),
and the Herfindahl index of business-segment revenue shares (segments axis 'BusinessSegments' only, optionally with ConsolidationItems; the revenue tag with
the most segment members; reconciling members 'other / eliminations / corporate / unallocated' and non-positive values dropped), with the segment count.
"""

import io
import os
import sys
import time
import urllib.error
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

from core.data import DATA_DIR
from core.edgar import load_constituents

OUT = DATA_DIR / "round69"
URL = "https://www.sec.gov/files/dera/data/financial-statement-data-sets/{y}q{q}.zip"
REV = ("Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet", "RevenueFromContractWithCustomerIncludingAssessedTax", "SalesRevenueGoodsNet", "SalesRevenueServicesNet")
SKIP = ("OTHER", "ELIMINAT", "CORPORATE", "UNALLOCATED", "INTERSEGMENT", "RECONCIL", "ALL OTHER", "TOTAL", "CONSOLIDAT")


def _download(y, q):
    headers = {"User-Agent": os.environ["SEC_CONTACT"], "Accept-Encoding": "identity"}
    for attempt in range(4):
        try:
            return urllib.request.urlopen(urllib.request.Request(URL.format(y=y, q=q), headers=headers), timeout=300).read()
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None
            time.sleep(3 + 3 * attempt)
        except Exception:
            time.sleep(3 + 3 * attempt)
    return None


def segment_members(seg):
    """Member of the BusinessSegments axis if the string uses only that axis (and ConsolidationItems), else None."""
    parts = [p for p in str(seg).split(";") if p]
    axes = {p.split("=")[0]: p.split("=", 1)[1] for p in parts if "=" in p}
    if "BusinessSegments" not in axes or not set(axes) <= {"BusinessSegments", "ConsolidationItems"}:
        return None
    return axes["BusinessSegments"]


def process(blob, ciks):
    z = zipfile.ZipFile(io.BytesIO(blob))
    names = {n.split("/")[-1].lower(): n for n in z.namelist()}
    sub = pd.read_csv(z.open(names["sub.txt"]), sep="\t", dtype=str, encoding="latin1", usecols=["adsh", "cik", "form", "period", "filed"])
    sub = sub[(sub["form"] == "10-K") & sub["cik"].astype(int).isin(ciks)]
    keep, period = set(sub["adsh"]), dict(zip(sub["adsh"], sub["period"]))
    parts = []
    for chunk in pd.read_csv(z.open(names["num.txt"]), sep="\t", dtype=str, encoding="latin1", usecols=["adsh", "tag", "ddate", "qtrs", "uom", "segments", "coreg", "value"], chunksize=2_000_000):
        parts.append(chunk[chunk["adsh"].isin(keep) & (chunk["uom"] == "USD") & chunk["coreg"].isna() & (chunk["qtrs"] == "4") & chunk["tag"].isin(REV)])
    num = pd.concat(parts, ignore_index=True)
    rows = []
    for adsh, g in num.groupby("adsh"):
        g = g[g["ddate"] == period[adsh]]
        total = bool(g["segments"].isna().any())
        seg = g[g["segments"].notna()].copy()
        seg["member"] = seg["segments"].map(segment_members)
        seg = seg.dropna(subset=["member"])
        if len(seg):
            seg = seg[[not any(k in m.upper() for k in SKIP) for m in seg["member"]]]
        seg["v"] = pd.to_numeric(seg["value"], errors="coerce")
        seg = seg[seg["v"] > 0]
        best_hhi, best_n = None, 0
        for tag, t in seg.groupby("tag"):
            t = t.drop_duplicates("member")
            if len(t) > best_n:
                share = t["v"] / t["v"].sum()
                best_hhi, best_n = float((share ** 2).sum()), len(t)
        rows.append({"adsh": adsh, "has_total": total, "n_seg": best_n, "hhi": best_hhi})
    res = pd.DataFrame(rows)
    return sub.merge(res, on="adsh") if len(res) else res


def one(args):
    y, q = args
    path = OUT / "q" / f"{y}q{q}.csv"
    if path.exists():
        return y, q, "cached"
    blob = _download(y, q)
    if blob is None:
        return y, q, "missing"
    try:
        frame = process(blob, set(load_constituents().values()))
    except Exception as exc:
        return y, q, f"ERROR {exc!r}"
    frame.to_csv(path, index=False)
    return y, q, len(frame)


def fetch(workers=3):
    (OUT / "q").mkdir(parents=True, exist_ok=True)
    jobs = [(y, q) for y in range(2015, pd.Timestamp.now().year + 1) for q in (1, 2, 3, 4) if (y, q) >= (2015, 4)]
    for r in ThreadPoolExecutor(workers).map(one, jobs):
        print(r, flush=True)
    frames = [pd.read_csv(p, dtype={"cik": int}) for p in sorted((OUT / "q").glob("*.csv")) if p.stat().st_size > 5]
    pd.concat(frames, ignore_index=True).to_csv(OUT / "filings.csv", index=False)
    print("done")


def load_filings() -> pd.DataFrame:
    return pd.read_csv(OUT / "filings.csv", dtype={"cik": int}, parse_dates=["filed", "period"], date_format="%Y%m%d")


if __name__ == "__main__":
    sys.exit(fetch())
