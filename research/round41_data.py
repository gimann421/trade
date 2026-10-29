"""Data for round 41 (research/r41-da-deferred-revenue-2026-10-29.md): D&A, deferred revenue, contract liabilities from SEC XBRL.

    PYTHONPATH=. python research/round41_data.py       # data/round41/facts.csv
"""

import pandas as pd

from core.data import DATA_DIR
from research import round25_data

OUT = DATA_DIR / "round41"
TAGS = ("DepreciationDepletionAndAmortization", "DeferredRevenue", "ContractWithCustomerLiability")


def fetch(workers: int = 6) -> pd.DataFrame:
    return round25_data.fetch(workers, tags=TAGS, out=OUT)


def load_facts() -> pd.DataFrame:
    return pd.read_csv(OUT / "facts.csv", parse_dates=["start", "end", "filed"])


if __name__ == "__main__":
    fetch()
