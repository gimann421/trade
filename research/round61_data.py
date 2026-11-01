"""Data for round 61 (research/r61-restate-deftax-allowance-2026-11-01.md): deferred tax and allowance tags, and comparative revision rates.

    PYTHONPATH=. python research/round61_data.py facts      # data/round61/facts.csv  (companyconcept tags)
    PYTHONPATH=. python research/round61_data.py revisions  # data/round61/revisions.csv (companyfacts: one summary row per 10-K)
"""

import json
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

from core.data import DATA_DIR
from core.edgar import HEADERS, load_constituents
from research import round25_data

OUT = DATA_DIR / "round61"
FACTS = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
TAGS = ("Assets", "NetIncomeLoss", "NetCashProvidedByUsedInOperatingActivities", "DeferredIncomeTaxExpenseBenefit", "DeferredIncomeTaxesAndTaxCredits",
        "AccountsReceivableAllowanceForCreditLossCurrent", "AllowanceForDoubtfulAccountsReceivableCurrent", "AccountsReceivableNetCurrent")
MIN_MATCHED = 30


def fetch_facts() -> pd.DataFrame:
    return round25_data.fetch(tags=TAGS, out=OUT)


def revision_rows(symbol: str, payload: dict) -> list[dict]:
    """One row per 10-K: fiscal year end, filing date, matched facts, revised facts. Comparatives are the prior-year facts the 10-K reports again."""
    rows = []
    for tag, body in payload.get("facts", {}).get("us-gaap", {}).items():
        for r in body.get("units", {}).get("USD", []):
            if str(r.get("form", "")).startswith("10-K") and r.get("accn"):
                rows.append((tag, r.get("start"), r["end"], r["val"], r["accn"], r["filed"]))
    if not rows:
        return []
    f = pd.DataFrame(rows, columns=["tag", "start", "end", "val", "accn", "filed"])
    f["end"], f["filed"] = pd.to_datetime(f["end"]), pd.to_datetime(f["filed"])
    f["start"] = pd.to_datetime(f["start"])
    dur = (f["end"] - f["start"]).dt.days
    f = f[f["start"].isna() | dur.between(350, 380)].sort_values(["filed", "accn"])
    first = f.groupby(["tag", "start", "end"], dropna=False).head(1)                   # first-filed 10-K value of each tag and period
    key = ["tag", "start", "end"]
    orig = first.set_index(key)[["val", "accn"]].rename(columns={"val": "orig", "accn": "orig_accn"})
    out = []
    for accn, g in f.groupby("accn"):
        cur_end = g["end"].max()
        prior = g[(g["end"] <= cur_end - pd.Timedelta(days=335)) & (g["end"] >= cur_end - pd.Timedelta(days=395))]
        if prior.empty:
            continue
        m = prior.join(orig, on=key)
        m = m[m["orig_accn"].notna() & (m["orig_accn"] != accn)]
        if m.empty:
            continue
        o = m["orig"].to_numpy(dtype=float)
        v = m["val"].to_numpy(dtype=float)
        changed = np.where(o == 0, v != 0, np.abs(v - o) > 0.005 * np.abs(o))
        out.append({"symbol": symbol, "accn": accn, "end": cur_end.date(), "filed": g["filed"].max().date(), "matched": len(m), "revised": int(changed.sum())})
    return out


def _one(symbol: str, cik: int):
    for attempt in range(3):
        try:
            req = urllib.request.Request(FACTS.format(cik=cik), headers=HEADERS)
            return revision_rows(symbol, json.loads(urllib.request.urlopen(req, timeout=120).read()))
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return []
            time.sleep(1 + attempt)
        except Exception:
            time.sleep(1 + attempt)
    return None


def fetch_revisions(workers: int = 4) -> pd.DataFrame:
    OUT.mkdir(parents=True, exist_ok=True)
    jobs = sorted(load_constituents().items())
    rows, failed = [], []
    with ThreadPoolExecutor(workers) as pool:
        for n, (job, result) in enumerate(zip(jobs, pool.map(lambda j: _one(*j), jobs)), 1):
            if result is None:
                failed.append(job[0])
            else:
                rows.extend(result)
            if n % 50 == 0:
                print(n, len(rows), len(failed), flush=True)
    frame = pd.DataFrame(rows)
    frame.to_csv(OUT / "revisions.csv", index=False)
    print("rows", len(frame), "symbols", frame["symbol"].nunique(), "failed", failed[:10])
    return frame


def load_facts() -> pd.DataFrame:
    return pd.read_csv(OUT / "facts.csv", parse_dates=["start", "end", "filed"])


def load_revisions() -> pd.DataFrame:
    return pd.read_csv(OUT / "revisions.csv", parse_dates=["end", "filed"])


if __name__ == "__main__":
    {"facts": fetch_facts, "revisions": fetch_revisions}[sys.argv[1]]()
