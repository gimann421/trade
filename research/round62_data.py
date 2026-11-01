"""Data for round 62 (research/r62-accrual-quality-inventory-mix-2026-11-01.md): inventory component tags.

    PYTHONPATH=. python research/round62_data.py       # data/round62/facts.csv  (companyconcept tags)
"""

import sys

import pandas as pd

from core.data import DATA_DIR
from research import round25_data

OUT = DATA_DIR / "round62"
TAGS = ("InventoryRawMaterialsNetOfReserves", "InventoryRawMaterials", "InventoryRawMaterialsAndSuppliesNetOfReserves", "InventoryRawMaterialsAndSupplies",
        "InventoryWorkInProcessNetOfReserves", "InventoryWorkInProcess", "InventoryFinishedGoodsNetOfReserves", "InventoryFinishedGoods")


def fetch_facts() -> pd.DataFrame:
    return round25_data.fetch(tags=TAGS, out=OUT)


def load_facts() -> pd.DataFrame:
    return pd.read_csv(OUT / "facts.csv", parse_dates=["start", "end", "filed"])


if __name__ == "__main__":
    fetch_facts()
