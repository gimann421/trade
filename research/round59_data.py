"""Data for round 59 (research/r59-equity-method-minority-2026-10-30.md): equity-method income and minority interest from SEC XBRL.

    PYTHONPATH=. python research/round59_data.py       # data/round59/facts.csv
"""

import pandas as pd

from core.data import DATA_DIR
from research import round25_data

OUT = DATA_DIR / "round59"
TAGS = ("IncomeLossFromEquityMethodInvestments", "MinorityInterest")


def fetch(workers: int = 6) -> pd.DataFrame:
    return round25_data.fetch(workers, tags=TAGS, out=OUT)


def load_facts() -> pd.DataFrame:
    return pd.read_csv(OUT / "facts.csv", parse_dates=["start", "end", "filed"])


if __name__ == "__main__":
    fetch()
