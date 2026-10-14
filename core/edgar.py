"""Earnings-release dates from SEC EDGAR: 8-K filings with Item 2.02, for the current S&P 500 constituents.

    python -m core.edgar     # downloads data/edgar/events.csv

Company numbers (CIK) come from the constituent file in fja05680/sp500 (current members only). Filings come from
data.sec.gov's submissions service: the "recent" block plus any older pages that reach back to 2015.
Requests are paced under the SEC's ten-per-second limit and carry a generic user agent.
"""

import csv
import io
import json
import time
import urllib.request

import numpy as np
import pandas as pd

from core.data import DATA_DIR

EDGAR_DIR = DATA_DIR / "edgar"
CONSTITUENTS_URL = "https://raw.githubusercontent.com/fja05680/sp500/master/sp500.csv"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/{name}"
HEADERS = {"User-Agent": "trade-research personal-research-script", "Accept-Encoding": "identity"}
EARLIEST = "2015-01-01"


def _get(url: str, headers=HEADERS, timeout: int = 60) -> bytes:
    return urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout).read()


def load_constituents() -> dict[str, int]:
    """Current S&P 500 symbol -> CIK."""
    text = _get(CONSTITUENTS_URL, headers={}).decode()
    return {r["Symbol"].strip(): int(r["CIK"]) for r in csv.DictReader(io.StringIO(text)) if r.get("CIK")}


def earnings_rows(block: dict) -> list[dict]:
    """8-K filings with Item 2.02 from one 'recent'-shaped block of parallel lists."""
    rows = []
    for k, form in enumerate(block["form"]):
        items = block["items"][k] or ""
        if form == "8-K" and "2.02" in [i.strip() for i in items.split(",")]:
            rows.append({"accession": block["accessionNumber"][k], "filing_date": block["filingDate"][k],
                         "acceptance_utc": block["acceptanceDateTime"][k], "items": items})
    return rows


def company_events(cik: int, fetch=_get, pause: float = 0.12) -> list[dict]:
    payload = json.loads(fetch(SUBMISSIONS_URL.format(name=f"CIK{cik:010d}.json")))
    rows = earnings_rows(payload["filings"]["recent"])
    for page in payload["filings"].get("files", []):
        if page.get("filingTo", "9999") >= EARLIEST:
            time.sleep(pause)
            rows += earnings_rows(json.loads(fetch(SUBMISSIONS_URL.format(name=page["name"]))))
    return rows


def download_events(pause: float = 0.12) -> dict:
    EDGAR_DIR.mkdir(parents=True, exist_ok=True)
    rows, errors = [], {}
    for symbol, cik in load_constituents().items():
        try:
            for r in company_events(cik, pause=pause):
                rows.append({"symbol": symbol, "cik": cik, **r})
        except Exception as exc:
            errors[symbol] = f"{type(exc).__name__}: {exc}"[:160]
        time.sleep(pause)
    frame = pd.DataFrame(rows).drop_duplicates(["cik", "accession"]).sort_values(["symbol", "acceptance_utc"])
    frame.to_csv(EDGAR_DIR / "events.csv", index=False)
    summary = {"events": len(frame), "symbols": int(frame["symbol"].nunique()), "errors": errors,
               "first": str(frame["filing_date"].min()), "last": str(frame["filing_date"].max())}
    (EDGAR_DIR / "manifest.json").write_text(json.dumps(summary, indent=1) + "\n")
    return summary


def load_events() -> pd.DataFrame:
    frame = pd.read_csv(EDGAR_DIR / "events.csv")
    frame["acceptance_utc"] = pd.to_datetime(frame["acceptance_utc"], utc=True)
    return frame


def reaction_sessions(acceptance_utc: pd.Series, sessions: pd.DatetimeIndex) -> pd.Series:
    """The session whose close first reflects each release: the same date if accepted before 09:30 New York
    time, otherwise the next session. Dates after the last session map to NaT."""
    local = acceptance_utc.dt.tz_convert("America/New_York")
    day = local.dt.tz_localize(None).dt.normalize()
    before_open = (local.dt.hour * 60 + local.dt.minute) < 9 * 60 + 30
    pos = sessions.searchsorted(day.to_numpy(), side="left")
    next_pos = sessions.searchsorted(day.to_numpy(), side="right")
    chosen = pd.Series(np.where(before_open.to_numpy(), pos, next_pos), index=acceptance_utc.index)
    valid = chosen < len(sessions)
    return pd.Series(sessions[chosen.where(valid, 0).to_numpy()], index=acceptance_utc.index).where(valid)


def main() -> None:
    print(json.dumps(download_events(), indent=1))


if __name__ == "__main__":
    main()
