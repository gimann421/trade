"""Data for round 60 (research/r60-asset-age-investments-2026-10-30.md): asset age and long-term investments from SEC XBRL.

    PYTHONPATH=. python research/round60_data.py       # data/round60/facts.csv
"""

import pandas as pd

from core.data import DATA_DIR
from research import round25_data

OUT = DATA_DIR / "round60"
TAGS = ("AccumulatedDepreciationDepletionAndAmortizationPropertyPlantAndEquipment", "PropertyPlantAndEquipmentGross", "LongTermInvestments")


def fetch(workers: int = 6) -> pd.DataFrame:
    return round25_data.fetch(workers, tags=TAGS, out=OUT)


def load_facts() -> pd.DataFrame:
    return pd.read_csv(OUT / "facts.csv", parse_dates=["start", "end", "filed"])


if __name__ == "__main__":
    fetch()
