"""Data for round 28 (research/r28-leverage-rnd-stability-2026-10-22.md): liabilities and R&D expense from SEC XBRL.

    PYTHONPATH=. python research/round28_data.py       # data/round28/facts.csv
"""

import pandas as pd

from core.data import DATA_DIR
from research import round25_data

OUT = DATA_DIR / "round28"
TAGS = ("Liabilities", "ResearchAndDevelopmentExpense")


def fetch(workers: int = 6) -> pd.DataFrame:
    round25_data.OUT, round25_data.TAGS = OUT, TAGS
    return round25_data.fetch(workers)


def load_facts() -> pd.DataFrame:
    return pd.read_csv(OUT / "facts.csv", parse_dates=["start", "end", "filed"])


if __name__ == "__main__":
    fetch()
