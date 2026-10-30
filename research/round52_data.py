"""Data for round 52 (research/r52-nonoperating-amortization-2026-10-30.md): other non-operating income and amortization of intangibles from SEC XBRL.

    PYTHONPATH=. python research/round52_data.py       # data/round52/facts.csv
"""

import pandas as pd

from core.data import DATA_DIR
from research import round25_data

OUT = DATA_DIR / "round52"
TAGS = ("OtherNonoperatingIncomeExpense", "AmortizationOfIntangibleAssets")


def fetch(workers: int = 6) -> pd.DataFrame:
    return round25_data.fetch(workers, tags=TAGS, out=OUT)


def load_facts() -> pd.DataFrame:
    return pd.read_csv(OUT / "facts.csv", parse_dates=["start", "end", "filed"])


if __name__ == "__main__":
    fetch()
