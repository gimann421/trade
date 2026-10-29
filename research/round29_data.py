"""Data for round 29 (research/r29-organizational-capital-2026-10-29.md): SG&A, advertising and goodwill from SEC XBRL.

    PYTHONPATH=. python research/round29_data.py       # data/round29/facts.csv
"""

import pandas as pd

from core.data import DATA_DIR
from research import round25_data

OUT = DATA_DIR / "round29"
TAGS = ("SellingGeneralAndAdministrativeExpense", "AdvertisingExpense", "Goodwill")


def fetch(workers: int = 6) -> pd.DataFrame:
    return round25_data.fetch(workers, tags=TAGS, out=OUT)


def load_facts() -> pd.DataFrame:
    return pd.read_csv(OUT / "facts.csv", parse_dates=["start", "end", "filed"])


if __name__ == "__main__":
    fetch()
