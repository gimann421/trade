"""Data for round 64 (research/r64-insider-13f-xbrl-benford-2026-11-02.md): SEC bulk data sets.

    SEC_CONTACT="Name <email>" PYTHONPATH=. python research/round64_data.py insider   # data/round64/insider.csv
    SEC_CONTACT=... PYTHONPATH=. python research/round64_data.py fsds                 # data/round64/fsds.csv, benford.csv
    SEC_CONTACT=... PYTHONPATH=. python research/round64_data.py f13                  # data/round64/f13_*.csv

Each quarterly zip is downloaded, reduced to the rows for current S&P 500 members (CIK map in core.edgar) and deleted; only the reduced files are kept in data/ (git-ignored).
SEC_CONTACT is read from the environment and used only in the User-Agent header.
"""

import io
import os
import sys
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from core.data import DATA_DIR
from core.edgar import load_constituents

OUT = DATA_DIR / "round64"
INS_URL = "https://www.sec.gov/files/structureddata/data/insider-transactions-data-sets/{q}_form345.zip"
FS_URL = "https://www.sec.gov/files/dera/data/financial-statement-data-sets/{q}.zip"
F13_BASE = "https://www.sec.gov/files/structureddata/data/form-13f-data-sets/"


def quarters(first, last):
    out = []
    for y in range(first[0], last[0] + 1):
        for q in range(1, 5):
            if (y, q) >= first and (y, q) <= last:
                out.append(f"{y}q{q}")
    return out


def download(url, dest: Path):
    headers = {"User-Agent": os.environ["SEC_CONTACT"], "Accept-Encoding": "identity"}
    for attempt in range(5):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=300) as r, open(dest, "wb") as f:
                while chunk := r.read(1 << 20):
                    f.write(chunk)
            return True
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return False
            time.sleep(2 + 3 * attempt)
        except Exception:
            time.sleep(2 + 3 * attempt)
    raise RuntimeError(f"download failed: {url}")


def cik_map():
    return {int(c): s for s, c in load_constituents().items()}


def fetch_insider(first=(2013, 1), last=(2026, 3)):
    OUT.mkdir(parents=True, exist_ok=True)
    ciks = cik_map()
    frames = []
    for q in quarters(first, last):
        with tempfile.TemporaryDirectory() as tmp:
            z = Path(tmp) / "a.zip"
            if not download(INS_URL.format(q=q), z):
                print(q, "not available", flush=True)
                continue
            with zipfile.ZipFile(z) as zf:
                sub = pd.read_csv(zf.open(_member(zf, "SUBMISSION.tsv")), sep="\t", dtype=str, usecols=["ACCESSION_NUMBER", "FILING_DATE", "DOCUMENT_TYPE", "ISSUERCIK"])
                sub = sub[sub["DOCUMENT_TYPE"].isin(["4", "4/A"])]
                sub["cik"] = sub["ISSUERCIK"].astype(int)
                sub = sub[sub["cik"].isin(ciks)]
                own = pd.read_csv(zf.open("REPORTINGOWNER.tsv"), sep="\t", dtype=str, usecols=["ACCESSION_NUMBER", "RPTOWNERCIK", "RPTOWNER_RELATIONSHIP", "RPTOWNER_TITLE"])
                tr = pd.read_csv(zf.open("NONDERIV_TRANS.tsv"), sep="\t", dtype=str,
                                 usecols=["ACCESSION_NUMBER", "SECURITY_TITLE", "TRANS_DATE", "TRANS_CODE", "TRANS_SHARES", "TRANS_PRICEPERSHARE", "TRANS_ACQUIRED_DISP_CD"])
            tr = tr[tr["TRANS_CODE"].isin(["P", "S"]) & tr["ACCESSION_NUMBER"].isin(sub["ACCESSION_NUMBER"])]
            m = tr.merge(sub[["ACCESSION_NUMBER", "FILING_DATE", "DOCUMENT_TYPE", "cik"]], on="ACCESSION_NUMBER").merge(own, on="ACCESSION_NUMBER")
            m["symbol"] = m["cik"].map(ciks)
            frames.append(m)
            print(q, len(m), flush=True)
    d = pd.concat(frames, ignore_index=True)
    d.columns = [c.lower() for c in d.columns]
    d.to_csv(OUT / "insider.csv", index=False)
    print("wrote", len(d))


def load_insider() -> pd.DataFrame:
    d = pd.read_csv(OUT / "insider.csv", dtype=str, keep_default_na=False)
    d["filed"] = pd.to_datetime(d["filing_date"], format="%d-%b-%Y")
    d["tdate"] = pd.to_datetime(d["trans_date"], format="%d-%b-%Y", errors="coerce")
    d["shares"] = pd.to_numeric(d["trans_shares"], errors="coerce")
    d["price"] = pd.to_numeric(d["trans_priceper_share"] if "trans_priceper_share" in d else d["trans_pricepershare"], errors="coerce")
    return d


def fetch_fsds(first=(2016, 1), last=(2026, 3)):
    OUT.mkdir(parents=True, exist_ok=True)
    ciks = cik_map()
    subs, ext, ben = [], [], []
    for q in quarters(first, last):
        with tempfile.TemporaryDirectory() as tmp:
            z = Path(tmp) / "a.zip"
            if not download(FS_URL.format(q=q), z):
                print(q, "not available", flush=True)
                continue
            with zipfile.ZipFile(z) as zf:
                sub = pd.read_csv(zf.open("sub.txt"), sep="\t", dtype=str, usecols=["adsh", "cik", "name", "form", "period", "filed", "fy", "fp"])
                sub = sub[(sub["form"] == "10-K") & sub["cik"].astype(int).isin(ciks)]
                keep = set(sub["adsh"])
                subs.append(sub)
                counts, digits = {}, {}
                seen = set()
                for chunk in pd.read_csv(zf.open("num.txt"), sep="\t", dtype=str, chunksize=2_000_000,
                                         usecols=["adsh", "tag", "version", "ddate", "qtrs", "uom", "segments", "coreg", "value"]):
                    chunk = chunk[chunk["adsh"].isin(keep) & (chunk["uom"] == "USD") & chunk["segments"].isna() & chunk["coreg"].isna()]
                    if chunk.empty:
                        continue
                    chunk = chunk.merge(sub[["adsh", "period"]], on="adsh")
                    chunk["val"] = pd.to_numeric(chunk["value"], errors="coerce")
                    chunk = chunk.dropna(subset=["val"]).drop_duplicates(["adsh", "tag", "ddate", "qtrs", "value"])
                    chunk["custom"] = chunk["version"] == chunk["adsh"]
                    # extension share: distinct tags for the current fiscal-year end
                    cur = chunk[chunk["ddate"] == chunk["period"]].drop_duplicates(["adsh", "tag"])
                    for adsh, g in cur.groupby("adsh"):
                        c = counts.setdefault(adsh, [0, 0])
                        c[0] += len(g)
                        c[1] += int(g["custom"].sum())
                    # Benford: first digit of all distinct values with |v| >= 10
                    big = chunk[chunk["val"].abs() >= 10]
                    fd = (big["val"].abs() / 10 ** np.floor(np.log10(big["val"].abs()))).astype(int)
                    for adsh, g in fd.groupby(big["adsh"]):
                        arr = digits.setdefault(adsh, np.zeros(10, dtype=int))
                        arr += np.bincount(g.to_numpy(), minlength=10)[:10]
                    del seen
                    seen = set()
            for adsh, (n, c) in counts.items():
                ext.append({"adsh": adsh, "ntags": n, "ncustom": c})
            for adsh, arr in digits.items():
                ben.append({"adsh": adsh, **{f"d{i}": int(arr[i]) for i in range(1, 10)}})
            print(q, len(sub), len(counts), flush=True)
    pd.concat(subs).merge(pd.DataFrame(ext), on="adsh", how="left").merge(pd.DataFrame(ben), on="adsh", how="left").to_csv(OUT / "fsds.csv", index=False)
    print("done")


def load_fsds() -> pd.DataFrame:
    d = pd.read_csv(OUT / "fsds.csv", dtype={"adsh": str, "cik": int})
    d["filed"] = pd.to_datetime(d["filed"].astype(str), format="%Y%m%d")
    d["period"] = pd.to_datetime(d["period"].astype(str), format="%Y%m%d")
    d["symbol"] = d["cik"].map(cik_map())
    return d


SUFFIX = {"INC", "CORP", "CORPORATION", "CO", "COMPANY", "LTD", "LIMITED", "PLC", "LLC", "LP", "HOLDINGS", "HLDGS", "GROUP", "GRP", "THE", "DE", "NEW", "COM", "CL", "CLASS", "A", "B", "C", "NV", "SA", "AG", "TRUST", "INCORPORATED", "INTERNATIONAL", "INTL", "SERIES", "ORD", "SHS", "CAP", "STK", "COMMON", "STOCK", "SHARES"}


def norm_name(name: str) -> str:
    import re
    words = re.sub(r"[^A-Z0-9 ]", " ", str(name).upper().replace("&", " AND ").replace("/", " ")).split()
    core = [w for w in words if w not in SUFFIX]
    return " ".join(core)


def f13_urls():
    import re
    page = urllib.request.urlopen(urllib.request.Request("https://www.sec.gov/data-research/sec-markets-data/form-13f-data-sets",
                                  headers={"User-Agent": os.environ["SEC_CONTACT"]}), timeout=60).read().decode()
    return sorted(set(re.findall(r"files/structureddata/data/form-13f-data-sets/([^\"]+\.zip)", page)))


def member_names():
    """normalised conformed company names (from the 10-K filings) -> symbol; ambiguous names dropped."""
    d = load_fsds()
    seen = {}
    for sym, name in zip(d["symbol"], d["name"]):
        seen.setdefault(norm_name(name), set()).add(sym)
    return {n: next(iter(s)) for n, s in seen.items() if len(s) == 1 and n}


def _member(zf, name):
    for n in zf.namelist():
        if n.upper().endswith(name.upper()):
            return n
    raise KeyError(f"{name} not in {zf.namelist()}")


def f13_read(zf):
    sub = pd.read_csv(zf.open(_member(zf, "SUBMISSION.tsv")), sep="\t", dtype=str, usecols=["ACCESSION_NUMBER", "FILING_DATE", "SUBMISSIONTYPE", "CIK", "PERIODOFREPORT"])
    sub = sub[sub["SUBMISSIONTYPE"] == "13F-HR"]
    return sub


def f13_cusips(zipname):
    """Pass 1: CUSIP -> modal normalised issuer name among common-share lines of one quarter file."""
    with tempfile.TemporaryDirectory() as tmp:
        z = Path(tmp) / "a.zip"
        download(F13_BASE + zipname, z)
        with zipfile.ZipFile(z) as zf:
            it = pd.read_csv(zf.open(_member(zf, "INFOTABLE.tsv")), sep="\t", dtype=str, usecols=["NAMEOFISSUER", "CUSIP", "SSHPRNAMTTYPE", "PUTCALL"])
    it = it[(it["SSHPRNAMTTYPE"] == "SH") & it["PUTCALL"].isna()]
    it["n"] = it["NAMEOFISSUER"].map(norm_name)
    top = it.groupby("CUSIP")["n"].agg(lambda s: s.value_counts().index[0])
    cnt = it.groupby("CUSIP").size()
    return pd.DataFrame({"name": top, "holders": cnt})


def fetch_f13(first="2013q2"):
    OUT.mkdir(parents=True, exist_ok=True)
    names = member_names()
    urls = f13_urls()
    cmap_path = OUT / "f13_cusip_map.csv"
    latest = urls[-1]
    cm = f13_cusips(latest)
    cm["symbol"] = cm["name"].map(names)
    cm = cm.dropna(subset=["symbol"]).sort_values("holders", ascending=False)
    cm = cm[cm["holders"] >= 20]
    cm.to_csv(cmap_path)
    print("cusips mapped", len(cm), "symbols", cm["symbol"].nunique(), "from", latest, flush=True)
    cusip_sym = cm["symbol"].to_dict()
    for zipname in urls:
        tag = zipname.replace("_form13f.zip", "")
        dest = OUT / f"f13_{tag}.csv"
        if dest.exists():
            continue
        with tempfile.TemporaryDirectory() as tmp:
            z = Path(tmp) / "a.zip"
            download(F13_BASE + zipname, z)
            with zipfile.ZipFile(z) as zf:
                sub = f13_read(zf)
                it = pd.read_csv(zf.open(_member(zf, "INFOTABLE.tsv")), sep="\t", dtype=str, usecols=["ACCESSION_NUMBER", "NAMEOFISSUER", "CUSIP", "SSHPRNAMTTYPE", "PUTCALL", "SSHPRNAMT"])
        it = it[(it["SSHPRNAMTTYPE"] == "SH") & it["PUTCALL"].isna() & it["ACCESSION_NUMBER"].isin(sub["ACCESSION_NUMBER"])]
        sym = it["CUSIP"].map(cusip_sym)
        byname = it["NAMEOFISSUER"].map(norm_name).map(names)
        it["symbol"] = sym.fillna(byname)
        it = it.dropna(subset=["symbol"])
        it["shares"] = pd.to_numeric(it["SSHPRNAMT"], errors="coerce")
        g = it.groupby(["ACCESSION_NUMBER", "symbol"], as_index=False)["shares"].sum()
        g = g.merge(sub[["ACCESSION_NUMBER", "FILING_DATE", "CIK", "PERIODOFREPORT"]], on="ACCESSION_NUMBER")
        g.drop(columns="ACCESSION_NUMBER").to_csv(dest, index=False)
        print(tag, len(sub), len(g), flush=True)


def load_f13() -> pd.DataFrame:
    parts = [pd.read_csv(p, dtype={"CIK": str}) for p in sorted(OUT.glob("f13_20*.csv")) + sorted(OUT.glob("f13_0*.csv")) + sorted(OUT.glob("f13_1*.csv"))]
    d = pd.concat(parts, ignore_index=True)
    d["filed"] = pd.to_datetime(d["FILING_DATE"], format="%d-%b-%Y")
    d["period"] = pd.to_datetime(d["PERIODOFREPORT"], format="%d-%b-%Y")
    return d


if __name__ == "__main__":
    {"insider": fetch_insider, "fsds": fetch_fsds, "f13": fetch_f13}[sys.argv[1]]()
