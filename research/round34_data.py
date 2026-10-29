"""Data for round 34 (research/r34-sbc-restructuring-2026-10-29.md): stock compensation and restructuring charges from SEC XBRL.

    PYTHONPATH=. python research/round34_data.py       # data/round34/facts.csv
"""

import pandas as pd

from core.data import DATA_DIR
from research import round25_data

OUT = DATA_DIR / "round34"
TAGS = ("ShareBasedCompensation", "RestructuringCharges")


def fetch(workers: int = 6) -> pd.DataFrame:
    return round25_data.fetch(workers, tags=TAGS, out=OUT)


def load_facts() -> pd.DataFrame:
    return pd.read_csv(OUT / "facts.csv", parse_dates=["start", "end", "filed"])


if __name__ == "__main__":
    fetch()
