"""Data for round 26 (research/r26-cashflow-fundamentals-2026-10-22.md): capex from SEC XBRL for the current S&P 500.

    PYTHONPATH=. python research/round26_data.py       # data/round26/facts.csv
"""

import pandas as pd

from core.data import DATA_DIR
from research import round25_data

OUT = DATA_DIR / "round26"
TAGS = ("PaymentsToAcquirePropertyPlantAndEquipment",)


def fetch(workers: int = 6) -> pd.DataFrame:
    round25_data.OUT, round25_data.TAGS = OUT, TAGS
    return round25_data.fetch(workers)


def load_facts() -> pd.DataFrame:
    return pd.read_csv(OUT / "facts.csv", parse_dates=["start", "end", "filed"])


if __name__ == "__main__":
    fetch()
