"""Data for round 57 (research/r57-pension-debtflow-2026-10-30.md): pension funded status and debt flows from SEC XBRL.

    PYTHONPATH=. python research/round57_data.py       # data/round57/facts.csv
"""

import pandas as pd

from core.data import DATA_DIR
from research import round25_data

OUT = DATA_DIR / "round57"
TAGS = ("DefinedBenefitPlanFundedStatusOfPlan", "ProceedsFromIssuanceOfLongTermDebt", "RepaymentsOfLongTermDebt")


def fetch(workers: int = 6) -> pd.DataFrame:
    return round25_data.fetch(workers, tags=TAGS, out=OUT)


def load_facts() -> pd.DataFrame:
    return pd.read_csv(OUT / "facts.csv", parse_dates=["start", "end", "filed"])


if __name__ == "__main__":
    fetch()
