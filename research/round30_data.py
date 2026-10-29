"""Data for round 30 (research/r30-cash-profit-tax-2026-10-29.md): cash, operating income, tax and interest expense from SEC XBRL.

    PYTHONPATH=. python research/round30_data.py       # data/round30/facts.csv
"""

import pandas as pd

from core.data import DATA_DIR
from research import round25_data

OUT = DATA_DIR / "round30"
TAGS = ("CashAndCashEquivalentsAtCarryingValue", "OperatingIncomeLoss", "IncomeTaxExpenseBenefit", "InterestExpense")


def fetch(workers: int = 6) -> pd.DataFrame:
    return round25_data.fetch(workers, tags=TAGS, out=OUT)


def load_facts() -> pd.DataFrame:
    return pd.read_csv(OUT / "facts.csv", parse_dates=["start", "end", "filed"])


if __name__ == "__main__":
    fetch()
