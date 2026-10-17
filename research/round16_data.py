"""Download daily bars for the round-16 ETF list into data/round16/ (git-ignored).

    PYTHONPATH=. python research/round16_data.py
"""

import json
import time
from datetime import datetime, timezone

import pandas as pd

from core.config import ROOT
from core.data import download_daily_bars, load_bars
from research.round16_common import ETFS

DIR = ROOT / "data" / "round16"
START = datetime(2015, 1, 2, tzinfo=timezone.utc)


def load_etfs() -> tuple[pd.DataFrame, pd.DataFrame]:
    """(close, volume) for every ETF with a downloaded file."""
    close, volume = {}, {}
    for s in ETFS:
        if (DIR / f"{s}_1Day.csv").exists():
            bars = load_bars(s, DIR)
            close[s], volume[s] = bars["close"], bars["volume"]
    return pd.DataFrame(close), pd.DataFrame(volume)


def main():
    DIR.mkdir(parents=True, exist_ok=True)
    missing = {}
    for s in ETFS:
        if (DIR / f"{s}_1Day.csv").exists():
            continue
        try:
            download_daily_bars(s, START, data_dir=DIR)
        except Exception as exc:
            missing[s] = f"{type(exc).__name__}: {exc}"[:120]
        time.sleep(0.3)
    close, _ = load_etfs()
    print(json.dumps({"downloaded": close.shape[1], "missing": missing, "first": str(close.index.min().date()),
                      "last": str(close.index.max().date())}, indent=1))


if __name__ == "__main__":
    main()
