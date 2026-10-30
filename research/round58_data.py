"""Data for round 58 (research/r58-aoci-otherassets-2026-10-30.md): AOCI and other non-current assets from SEC XBRL.

    PYTHONPATH=. python research/round58_data.py       # data/round58/facts.csv
"""

import pandas as pd

from core.data import DATA_DIR
from research import round25_data

OUT = DATA_DIR / "round58"
TAGS = ("AccumulatedOtherComprehensiveIncomeLossNetOfTax", "OtherAssetsNoncurrent")


def fetch(workers: int = 6) -> pd.DataFrame:
    return round25_data.fetch(workers, tags=TAGS, out=OUT)


def load_facts() -> pd.DataFrame:
    return pd.read_csv(OUT / "facts.csv", parse_dates=["start", "end", "filed"])


if __name__ == "__main__":
    fetch()
