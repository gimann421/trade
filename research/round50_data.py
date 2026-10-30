"""Data for round 50 (research/r50-acquisitions-payables-2026-10-30.md): cash paid for acquisitions, accounts payable from SEC XBRL.

    PYTHONPATH=. python research/round50_data.py       # data/round50/facts.csv
"""

import pandas as pd

from core.data import DATA_DIR
from research import round25_data

OUT = DATA_DIR / "round50"
TAGS = ("PaymentsToAcquireBusinessesNetOfCashAcquired", "AccountsPayableCurrent")


def fetch(workers: int = 6) -> pd.DataFrame:
    return round25_data.fetch(workers, tags=TAGS, out=OUT)


def load_facts() -> pd.DataFrame:
    return pd.read_csv(OUT / "facts.csv", parse_dates=["start", "end", "filed"])


if __name__ == "__main__":
    fetch()
