"""Data for round 24 (research/r24-dividends-2026-10-20.md): cash dividends for every S&P 500 member ticker, from Alpaca corporate actions.

    PYTHONPATH=. python research/round24_data.py       # data/round24/dividends.csv

Each row: symbol, ex_date, process_date, record_date, payable_date, rate (cash per share), special. Alpaca gives the ex-date and the payment details;
no declaration date, so a dividend is treated as known only from its ex-date (later than the market knew it: conservative for event signals).
"""

import sys
import time
from datetime import date

import pandas as pd
from alpaca.data.historical.corporate_actions import CorporateActionsClient
from alpaca.data.requests import CorporateActionsRequest

from core.config import load_paper_keys
from core.data import DATA_DIR
from core.universe import last_member_dates, load_membership

OUT = DATA_DIR / "round24"
START, END = date(2015, 1, 1), date(2026, 10, 15)


def fetch(batch: int = 20) -> pd.DataFrame:
    keys = load_paper_keys()
    client = CorporateActionsClient(keys.api_key, keys.secret_key)
    symbols = sorted(last_member_dates(load_membership()))
    rows = []
    for i in range(0, len(symbols), batch):
        chunk = symbols[i:i + batch]
        for attempt in range(3):
            try:
                result = client.get_corporate_actions(CorporateActionsRequest(symbols=chunk, start=START, end=END, types=["cash_dividend"]))
                break
            except Exception as exc:  # retry the chunk, then fall back to single symbols
                time.sleep(2 * (attempt + 1))
                result = None
        if result is None:
            print("chunk failed", chunk[0], flush=True)
            continue
        for r in result.data.get("cash_dividends", []):
            rows.append({"symbol": r.symbol, "ex_date": r.ex_date, "process_date": r.process_date, "record_date": r.record_date,
                         "payable_date": r.payable_date, "rate": r.rate, "special": r.special, "foreign": r.foreign})
        if (i // batch) % 10 == 0:
            print(i, len(rows), flush=True)
        time.sleep(0.3)
    frame = pd.DataFrame(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    frame.to_csv(OUT / "dividends.csv", index=False)
    print(f"{len(frame)} dividends, {frame.symbol.nunique()} of {len(symbols)} symbols with at least one")
    return frame


def load_dividends() -> pd.DataFrame:
    frame = pd.read_csv(OUT / "dividends.csv", parse_dates=["ex_date", "process_date", "record_date", "payable_date"])
    frame["ex_date"] = frame["ex_date"].fillna(frame["process_date"])
    return frame.dropna(subset=["ex_date", "rate"])


if __name__ == "__main__":
    fetch()
