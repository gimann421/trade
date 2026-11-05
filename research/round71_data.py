"""Data for round 71 (research/r71-trials-recalls-2026-11-05.md): ClinicalTrials.gov Phase 2/3 trials and openFDA recalls for SIC 28 / 38 members.

    PYTHONPATH=. python research/round71_data.py trials    # data/round71/trials.csv
    PYTHONPATH=. python research/round71_data.py recalls   # data/round71/recalls.csv

Members: current S&P 500 members whose 2-digit SIC is 28 (chemicals and drugs) or 38 (instruments, devices). A record is kept only when the
normalised sponsor name equals or starts with (trials) / the normalised recalling-firm name equals (recalls) the normalised SEC name or one of its three most recent former names (no hand matching).
trials: lead sponsor, NCT id, phase, first-posted date, primary completion date (the CURRENT registry value, not the date planned at the time:
the pipeline rule therefore looks ahead and is reported with that caveat). recalls: drug and device enforcement reports with the report date.
"""

import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

from core.data import DATA_DIR
from core.edgar import load_constituents
from core.industry import load_sic
from research import round44_data

OUT = DATA_DIR / "round71"
UA = {"User-Agent": "trade-research personal-research-script", "Accept": "application/json"}
SUFFIX = re.compile(r"\b(INC|INCORPORATED|CORP|CORPORATION|CO|COMPANY|LTD|LIMITED|PLC|LLC|LP|NV|SA|AG|THE|DE)\b")
CT = "https://clinicaltrials.gov/api/v2/studies?query.lead={q}&filter.advanced=AREA%5BPhase%5D%28PHASE2%20OR%20PHASE3%29&pageSize=1000&fields=NCTId,LeadSponsorName,Phase,StudyFirstPostDate,PrimaryCompletionDate"
FDA = "https://api.fda.gov/{kind}/enforcement.json?search=recalling_firm:%22{q}%22&limit=1000"


def norm(name):
    s = re.sub(r"[^A-Z0-9 ]", " ", str(name).upper().replace("&", " AND "))
    return re.sub(r"\s+", " ", SUFFIX.sub(" ", s)).strip()


def _get(url):
    for attempt in range(5):
        try:
            return json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=90).read())
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None
            time.sleep(2 + 2 * attempt)
        except Exception:
            time.sleep(2 + 2 * attempt)
    return None


def jobs():
    sic = load_sic().astype(int)
    out = []
    for symbol, cik in sorted(load_constituents().items()):
        if symbol in sic.index and sic[symbol] in (28, 38):
            top = round44_data._get(f"CIK{cik:010d}.json")
            if top:
                out.append((symbol, [top["name"]] + [f["name"] for f in top.get("formerNames", [])[:3]]))
    return out


def _trials(job):
    symbol, names = job
    keys = {norm(n) for n in names}
    rows, seen = [], set()
    for name in names[:2]:
        url = CT.format(q=urllib.parse.quote(norm(name)))
        while url:
            d = _get(url)
            if not d:
                break
            for s in d.get("studies", []):
                p = s["protocolSection"]
                nct = p["identificationModule"]["nctId"]
                lead = p["sponsorCollaboratorsModule"]["leadSponsor"]["name"]
                if any(norm(lead) == k or (len(k) >= 4 and norm(lead).startswith(k + " ")) for k in keys) and nct not in seen:
                    seen.add(nct)
                    st = p["statusModule"]
                    rows.append((symbol, nct, lead, "|".join(p["designModule"].get("phases", [])), st.get("studyFirstPostDateStruct", {}).get("date"),
                                 st.get("primaryCompletionDateStruct", {}).get("date")))
            tok = d.get("nextPageToken")
            url = CT.format(q=urllib.parse.quote(norm(name))) + "&pageToken=" + tok if tok else None
    return symbol, rows


def _recalls(job):
    symbol, names = job
    keys = {norm(n) for n in names}
    rows, seen = [], set()
    for name in names[:2]:
        for kind in ("drug", "device"):
            d = _get(FDA.format(kind=kind, q=urllib.parse.quote(norm(name))))
            for r in (d or {}).get("results", []):
                if norm(r.get("recalling_firm", "")) in keys and r.get("recall_number") not in seen:
                    seen.add(r.get("recall_number"))
                    rows.append((symbol, kind, r.get("recall_number"), r.get("recalling_firm"), r.get("report_date"), r.get("classification")))
    return symbol, rows


def fetch(kind):
    OUT.mkdir(parents=True, exist_ok=True)
    fn, cols = (_trials, ["symbol", "nct", "lead", "phases", "first_posted", "primary_completion"]) if kind == "trials" else (_recalls, ["symbol", "kind", "recall_number", "firm", "report_date", "classification"])
    js = jobs()
    rows = []
    with ThreadPoolExecutor(4) as pool:
        for n, (symbol, r) in enumerate(pool.map(fn, js), 1):
            rows.extend(r)
            if n % 20 == 0:
                print(n, len(js), len(rows), flush=True)
    pd.DataFrame(rows, columns=cols).to_csv(OUT / f"{kind}.csv", index=False)
    print("done", kind, len(js), "members,", len(rows), "records,", len({r[0] for r in rows}), "members with records")


def load_trials() -> pd.DataFrame:
    t = pd.read_csv(OUT / "trials.csv")
    t["posted"] = pd.to_datetime(t["first_posted"], errors="coerce")
    t["complete"] = pd.to_datetime(t["primary_completion"], errors="coerce")
    return t


def load_recalls() -> pd.DataFrame:
    r = pd.read_csv(OUT / "recalls.csv", dtype=str)
    r["reported"] = pd.to_datetime(r["report_date"], format="%Y%m%d", errors="coerce")
    return r


if __name__ == "__main__":
    fetch(sys.argv[1])
