"""Data for round 35 (research/r35-balance-sheet-levels-2026-10-29.md): current assets/liabilities, retained earnings, treasury stock from SEC XBRL.

    PYTHONPATH=. python research/round35_data.py       # data/round35/facts.csv
"""

import pandas as pd

from core.data import DATA_DIR
from research import round25_data

OUT = DATA_DIR / "round35"
TAGS = ("AssetsCurrent", "LiabilitiesCurrent", "RetainedEarningsAccumulatedDeficit", "TreasuryStockValue")


def fetch(workers: int = 6) -> pd.DataFrame:
    return round25_data.fetch(workers, tags=TAGS, out=OUT)


def load_facts() -> pd.DataFrame:
    return pd.read_csv(OUT / "facts.csv", parse_dates=["start", "end", "filed"])


if __name__ == "__main__":
    fetch()
