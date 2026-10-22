"""Data for round 27 (research/r27-working-capital-2026-10-22.md): receivables, inventory and revenue from SEC XBRL.

    PYTHONPATH=. python research/round27_data.py       # data/round27/facts.csv
"""

import pandas as pd

from core.data import DATA_DIR
from research import round25_data

OUT = DATA_DIR / "round27"
TAGS = ("AccountsReceivableNetCurrent", "InventoryNet", "Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax")


def fetch(workers: int = 6) -> pd.DataFrame:
    round25_data.OUT, round25_data.TAGS = OUT, TAGS
    return round25_data.fetch(workers)


def load_facts() -> pd.DataFrame:
    return pd.read_csv(OUT / "facts.csv", parse_dates=["start", "end", "filed"])


if __name__ == "__main__":
    fetch()
