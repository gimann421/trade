"""Downloads for round 13 (research/r13-novel-ideas-2026-10-15.md). Everything lands in data/ (gitignored).

    python -m research.round13_data finra     # FINRA daily short-sale volume (consolidated NMS files), member tickers only
    python -m research.round13_data filings   # every 8-K (all items) for the current S&P 500, from SEC submissions
    python -m research.round13_data insider   # SEC insider transactions data sets, open-market purchases (code P)
    python -m research.round13_data wiki      # Wikipedia daily page views of the current members' articles
    python -m research.round13_data spy       # SPY 15:30/15:45/close snapshots
"""

import argparse
import io
import json
import re
import time
import urllib.error
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import pandas as pd

from core.data import DATA_DIR
from core.edgar import EDGAR_DIR, SUBMISSIONS_URL, load_constituents
from core.universe import STOCK_DIR

UA = {"User-Agent": "trade-research personal-research-script (garret.mann.421@gmail.com)", "Accept-Encoding": "identity"}
FINRA_URL = "https://cdn.finra.org/equity/regsho/daily/CNMSshvol{d}.txt"
FINRA_PATH = DATA_DIR / "finra" / "shvol.csv"
FILINGS_PATH = EDGAR_DIR / "all_8k.csv"
INSIDER_PATH = DATA_DIR / "insider" / "purchases.csv"
WIKI_DIR = DATA_DIR / "wiki"
SPY_PATH = DATA_DIR / "spy_snapshots.csv"


def get(url: str, timeout: int = 60, tries: int = 4) -> bytes | None:
    for k in range(tries):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout).read()
        except urllib.error.HTTPError as exc:
            if exc.code in (403, 404):
                return None
            time.sleep(2 ** k)
        except Exception:
            time.sleep(2 ** k)
    return None


def member_tickers() -> set[str]:
    return {p.name.rsplit("_1Day", 1)[0] for p in STOCK_DIR.glob("*_1Day.csv")}


def finra(start="2018-01-01"):
    wanted = member_tickers()
    days = pd.bdate_range(start, pd.Timestamp.now().normalize())

    def one(day):
        body = get(FINRA_URL.format(d=day.strftime("%Y%m%d")))
        if body is None:
            return day, None
        frame = pd.read_csv(io.BytesIO(body), sep="|", dtype={"Symbol": str})
        frame = frame[frame["Symbol"].isin(wanted)]
        return day, frame[["Date", "Symbol", "ShortVolume", "TotalVolume"]]

    parts, missing = [], []
    with ThreadPoolExecutor(6) as pool:
        for day, frame in pool.map(one, days):
            (parts.append(frame) if frame is not None else missing.append(day))
    out = pd.concat(parts).sort_values(["Symbol", "Date"])
    FINRA_PATH.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(FINRA_PATH, index=False)
    first = out["Date"].min()
    print(f"finra: {len(parts)} days, {len(out)} rows, first {first}, symbols {out['Symbol'].nunique()}, "
          f"missing weekdays after first: {sum(str(d.date()).replace('-', '') > str(first) for d in missing)}")


def filings():
    rows = []
    for symbol, cik in load_constituents().items():
        body = get(SUBMISSIONS_URL.format(name=f"CIK{cik:010d}.json"))
        time.sleep(0.12)
        if body is None:
            continue
        payload = json.loads(body)
        blocks = [payload["filings"]["recent"]]
        for page in payload["filings"].get("files", []):
            if page.get("filingTo", "9999") >= "2015-01-01":
                more = get(SUBMISSIONS_URL.format(name=page["name"]))
                time.sleep(0.12)
                if more:
                    blocks.append(json.loads(more))
        for b in blocks:
            for k, form in enumerate(b["form"]):
                if form == "8-K":
                    rows.append({"symbol": symbol, "cik": cik, "accession": b["accessionNumber"][k], "filing_date": b["filingDate"][k],
                                 "acceptance_utc": b["acceptanceDateTime"][k], "items": b["items"][k] or ""})
    frame = pd.DataFrame(rows).drop_duplicates(["cik", "accession"]).sort_values(["symbol", "acceptance_utc"])
    frame.to_csv(FILINGS_PATH, index=False)
    print(f"filings: {len(frame)} 8-Ks, {frame['symbol'].nunique()} symbols, {frame['filing_date'].min()}..{frame['filing_date'].max()}")


def insider():
    keep = []
    now = pd.Timestamp.now()
    for year in range(2016, now.year + 1):
        for q in (1, 2, 3, 4):
            if year == 2016 and q < 4 or pd.Timestamp(year=year, month=3 * q - 2, day=1) > now:
                continue
            body = get(f"https://www.sec.gov/files/structureddata/data/insider-transactions-data-sets/{year}q{q}_form345.zip", timeout=180)
            time.sleep(0.3)
            if body is None:
                print(f"insider: no file for {year}q{q}")
                continue
            z = zipfile.ZipFile(io.BytesIO(body))
            rd = lambda name: pd.read_csv(z.open(name), sep="\t", dtype=str, low_memory=False)
            sub, own, tr = rd("SUBMISSION.tsv"), rd("REPORTINGOWNER.tsv"), rd("NONDERIV_TRANS.tsv")
            tr = tr[(tr["TRANS_CODE"] == "P") & (tr["TRANS_ACQUIRED_DISP_CD"] == "A")]
            sub = sub[sub["DOCUMENT_TYPE"].isin(["4", "4/A"])][["ACCESSION_NUMBER", "FILING_DATE", "ISSUERCIK", "ISSUERTRADINGSYMBOL", "DOCUMENT_TYPE"]]
            own = own[["ACCESSION_NUMBER", "RPTOWNERCIK", "RPTOWNER_RELATIONSHIP"]]
            merged = tr.merge(sub, on="ACCESSION_NUMBER").merge(own, on="ACCESSION_NUMBER")
            keep.append(merged[["ACCESSION_NUMBER", "FILING_DATE", "ISSUERCIK", "ISSUERTRADINGSYMBOL", "RPTOWNERCIK", "RPTOWNER_RELATIONSHIP",
                                "TRANS_DATE", "TRANS_SHARES", "TRANS_PRICEPERSHARE", "DOCUMENT_TYPE"]])
            print(f"insider: {year}q{q} {len(merged)} purchase rows", flush=True)
    out = pd.concat(keep)
    INSIDER_PATH.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(INSIDER_PATH, index=False)


def wiki():
    page = get("https://en.wikipedia.org/w/api.php?action=parse&page=List_of_S%26P_500_companies&prop=text&format=json&formatversion=2")
    html = json.loads(page)["parse"]["text"]
    table = html.split('id="constituents"', 1)[1].split("</table>", 1)[0]
    pairs = {}
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", table, flags=re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, flags=re.S)
        if len(cells) < 2:
            continue
        ticker = re.sub(r"<.*?>", "", cells[0]).strip()
        link = re.search(r'href="(?:https://en\.wikipedia\.org)?/wiki/([^"#]+)"', cells[1])
        if ticker and link:
            pairs[ticker] = link.group(1)
    WIKI_DIR.mkdir(parents=True, exist_ok=True)
    (WIKI_DIR / "titles.json").write_text(json.dumps(pairs, indent=1, sort_keys=True))
    end = (pd.Timestamp.now() - pd.Timedelta(days=2)).strftime("%Y%m%d")

    def one(item):
        ticker, title = item
        body = get(f"https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/user/{title}/daily/20150701/{end}", timeout=60)
        time.sleep(0.6)
        if body is None:
            return ticker, None
        rows = json.loads(body)["items"]
        return ticker, pd.Series({pd.Timestamp(r["timestamp"][:8]): r["views"] for r in rows}, name=ticker)

    series, failed = [], []
    done = pd.read_csv(WIKI_DIR / "views.csv", index_col=0, parse_dates=True) if (WIKI_DIR / "views.csv").exists() else None
    if done is not None:
        series = [done[c] for c in done.columns]
        pairs = {k: v for k, v in pairs.items() if k not in done.columns}
    with ThreadPoolExecutor(1) as pool:
        for ticker, s in pool.map(one, pairs.items()):
            (series.append(s) if s is not None else failed.append(ticker))
    out = pd.concat(series, axis=1).sort_index()
    out.index.name = "date"
    out.to_csv(WIKI_DIR / "views.csv")
    print(f"wiki: {len(series)} articles, {len(failed)} failed {failed[:10]}, {out.index.min().date()}..{out.index.max().date()}")


def spy():
    from alpaca.data.enums import Adjustment
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
    from core.config import load_paper_keys
    keys = load_paper_keys()
    client = StockHistoricalDataClient(keys.api_key, keys.secret_key)
    request = StockBarsRequest(symbol_or_symbols="SPY", timeframe=TimeFrame(15, TimeFrameUnit.Minute), start=datetime(2016, 12, 1, tzinfo=timezone.utc),
                               end=pd.Timestamp.now("UTC").to_pydatetime() - pd.Timedelta(minutes=20), adjustment=Adjustment.ALL)
    df = client.get_stock_bars(request).df
    df = df.xs("SPY", level="symbol") if isinstance(df.index, pd.MultiIndex) else df
    df.index = pd.to_datetime(df.index).tz_convert("America/New_York")
    minutes = df.index.hour * 60 + df.index.minute
    day = pd.Series(df.index.date, index=df.index)
    at = lambda m: df["close"][minutes == m].groupby(day[minutes == m].values).last()
    out = pd.DataFrame({"p1530": at(15 * 60 + 15), "p1545": at(15 * 60 + 30), "close": at(15 * 60 + 45)})
    out.index = pd.to_datetime(out.index)
    out.index.name = "date"
    out.to_csv(SPY_PATH)
    print(f"spy: {len(out)} sessions {out.index.min().date()}..{out.index.max().date()}")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("what", choices=["finra", "filings", "insider", "wiki", "spy"])
    args = parser.parse_args()
    {"finra": finra, "filings": filings, "insider": insider, "wiki": wiki, "spy": spy}[args.what]()


if __name__ == "__main__":
    main()
