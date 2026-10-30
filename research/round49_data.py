"""Data for round 49 (research/r49-payout-tangibility-2026-10-30.md): buybacks, dividends paid, net PP&E from SEC XBRL.

    PYTHONPATH=. python research/round49_data.py       # data/round49/facts.csv
"""

import pandas as pd

from core.data import DATA_DIR
from research import round25_data

OUT = DATA_DIR / "round49"
TAGS = ("PaymentsForRepurchaseOfCommonStock", "PaymentsOfDividends", "PaymentsOfDividendsCommonStock", "PropertyPlantAndEquipmentNet")


def fetch(workers: int = 6) -> pd.DataFrame:
    return round25_data.fetch(workers, tags=TAGS, out=OUT)


def load_facts() -> pd.DataFrame:
    return pd.read_csv(OUT / "facts.csv", parse_dates=["start", "end", "filed"])


if __name__ == "__main__":
    fetch()
