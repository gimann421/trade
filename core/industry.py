"""SIC industry codes for the current S&P 500 constituents, from the same SEC submissions service as core.edgar.

    python -m core.industry     # downloads data/edgar/sic.csv (symbol, cik, sic, sic_description)

Current members only: delisted names have no company number in the constituent file, so they have no code.
"""

import json
import time

import pandas as pd

from core.edgar import EDGAR_DIR, SUBMISSIONS_URL, _get, load_constituents

SIC_PATH = EDGAR_DIR / "sic.csv"


def download_sic(pause: float = 0.12) -> pd.DataFrame:
    EDGAR_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    for symbol, cik in load_constituents().items():
        try:
            payload = json.loads(_get(SUBMISSIONS_URL.format(name=f"CIK{cik:010d}.json")))
            rows.append({"symbol": symbol, "cik": cik, "sic": payload.get("sic") or "", "sic_description": payload.get("sicDescription") or ""})
        except Exception as exc:  # keep going; a missing code means the name falls back to the market group
            rows.append({"symbol": symbol, "cik": cik, "sic": "", "sic_description": f"error {type(exc).__name__}"})
        time.sleep(pause)
    frame = pd.DataFrame(rows)
    frame.to_csv(SIC_PATH, index=False)
    return frame


def load_sic() -> pd.Series:
    """Symbol -> two-digit SIC major group (as a string), for symbols that have a code."""
    frame = pd.read_csv(SIC_PATH, dtype=str).fillna("")
    frame = frame[frame["sic"].str.len() >= 2]
    return frame.set_index("symbol")["sic"].str[:2]


if __name__ == "__main__":
    frame = download_sic()
    print(f"{len(frame)} symbols, {(frame['sic'] != '').sum()} with a code, {frame['sic'].str[:2].nunique()} major groups")
