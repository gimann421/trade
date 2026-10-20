"""Data for round 22 (research/r22-vol-term-structure-2026-10-20.md): Cboe index histories.

    PYTHONPATH=. python research/round22_data.py       # data/cboe/{VIX,VIX3M,VIX9D,VVIX,SKEW}.csv
"""

import urllib.request

import pandas as pd

from core.data import DATA_DIR

OUT = DATA_DIR / "cboe"
URL = "https://cdn.cboe.com/api/global/us_indices/daily_prices/{name}_History.csv"
NAMES = ("VIX", "VIX3M", "VIX9D", "VVIX", "SKEW")


def fetch() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name in NAMES:
        body = urllib.request.urlopen(URL.format(name=name), timeout=60).read()
        (OUT / f"{name}.csv").write_bytes(body)
        print(name, len(body))


def load(name: str) -> pd.Series:
    """Daily close of a Cboe index (the last column of the history file)."""
    frame = pd.read_csv(OUT / f"{name}.csv")
    frame["DATE"] = pd.to_datetime(frame["DATE"], format="%m/%d/%Y")
    return frame.set_index("DATE").iloc[:, -1].astype(float).rename(name)


if __name__ == "__main__":
    fetch()
