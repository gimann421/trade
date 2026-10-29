"""Data for round 33 (research/r33-corporate-actions-2026-10-29.md): splits and spin-offs from Alpaca corporate actions for every S&P 500 member ticker.

    PYTHONPATH=. python research/round33_data.py       # data/round33/splits.csv, data/round33/spinoffs.csv
Special dividends come from round 24 (data/round24/dividends.csv, special flag). An event is known from its ex-date.
"""

import time
from datetime import date

import pandas as pd
from alpaca.data.historical.corporate_actions import CorporateActionsClient
from alpaca.data.requests import CorporateActionsRequest

from core.config import load_paper_keys
from core.data import DATA_DIR
from core.universe import last_member_dates, load_membership

OUT = DATA_DIR / "round33"
START, END = date(2015, 1, 1), date(2026, 10, 15)


def fetch(batch: int = 20):
    keys = load_paper_keys()
    client = CorporateActionsClient(keys.api_key, keys.secret_key)
    symbols = sorted(last_member_dates(load_membership()))
    splits, spins = [], []
    for i in range(0, len(symbols), batch):
        chunk = symbols[i:i + batch]
        result = None
        for attempt in range(3):
            try:
                result = client.get_corporate_actions(CorporateActionsRequest(symbols=chunk, start=START, end=END, types=["forward_split", "spin_off"]))
                break
            except Exception:
                time.sleep(2 * (attempt + 1))
        if result is None:
            print("chunk failed", chunk[0], flush=True)
            continue
        for r in result.data.get("forward_splits", []):
            splits.append({"symbol": r.symbol, "ex_date": r.ex_date, "new_rate": r.new_rate, "old_rate": r.old_rate})
        for r in result.data.get("spin_offs", []):
            spins.append({"symbol": r.source_symbol, "new_symbol": r.new_symbol, "ex_date": r.ex_date})
        time.sleep(0.3)
    OUT.mkdir(parents=True, exist_ok=True)
    splits, spins = pd.DataFrame(splits), pd.DataFrame(spins)
    splits.to_csv(OUT / "splits.csv", index=False)
    spins.to_csv(OUT / "spinoffs.csv", index=False)
    print(len(splits), "forward splits;", len(spins), "spin-offs;", len(symbols), "symbols")
    return splits, spins


def load_events():
    splits = pd.read_csv(OUT / "splits.csv", parse_dates=["ex_date"])
    splits = splits[splits["new_rate"] / splits["old_rate"] >= 1.5]
    spins = pd.read_csv(OUT / "spinoffs.csv", parse_dates=["ex_date"])
    return splits, spins


if __name__ == "__main__":
    fetch()
