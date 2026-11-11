"""Convert a Sharadar equity-prices (SEP) export into the repo's per-ticker daily bar files, and report how
much of the 2000-2015 S&P 500 it covers. Files land in data/long/sharadar/ (gitignored), one `<TICKER>_1Day.csv`
per ticker in the layout of core.data.load_bars.

    python -m core.sharadar convert SHARADAR_SEP.csv      # or the .zip the bulk download delivers
    python -m core.sharadar coverage                      # share of point-in-time members with bars, by year

Expected columns (Nasdaq Data Link's published SEP layout, not yet checked against a real file):
ticker, date, open, high, low, close, volume, closeadj, closeunadj. `close` is split-adjusted; `closeadj` also
carries dividends. Open, high, low and close are scaled by closeadj / close so the files match the dividend-adjusted
convention of the Alpaca and Yahoo bars. The file is read in chunks and cut to 1998-2015 so nothing later is kept.
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from core.data import COLUMNS, DATA_DIR

SHARADAR_DIR = DATA_DIR / "long" / "sharadar"
START, END = "1998-01-01", "2015-12-31"
NEEDED = ["ticker", "date", "open", "high", "low", "close", "volume", "closeadj"]


def adjust(frame: pd.DataFrame) -> pd.DataFrame:
    """Rows of one export chunk -> date-indexed open/high/low/close/volume, dividend-adjusted."""
    missing = [c for c in NEEDED if c not in frame.columns]
    if missing:
        raise ValueError(f"export lacks columns {missing}; has {list(frame.columns)}")
    factor = frame["closeadj"] / frame["close"]
    out = pd.DataFrame({"ticker": frame["ticker"], "date": pd.to_datetime(frame["date"])})
    for column in ("open", "high", "low"):
        out[column] = frame[column] * factor
    out["close"] = frame["closeadj"]
    out["volume"] = frame["volume"]
    out = out.replace([np.inf, -np.inf], np.nan).dropna(subset=["close"])
    return out[(out["close"] > 0) & (out["date"] >= START) & (out["date"] <= END)]


def convert(source: Path, out_dir: Path = SHARADAR_DIR, chunksize: int = 1_000_000) -> dict:
    """Write one bar file per ticker; returns counts. Existing files in out_dir are replaced."""
    out_dir.mkdir(parents=True, exist_ok=True)
    pieces: dict[str, list[pd.DataFrame]] = {}
    rows = 0
    for chunk in pd.read_csv(source, usecols=NEEDED, chunksize=chunksize):
        chunk = adjust(chunk)
        rows += len(chunk)
        for ticker, part in chunk.groupby("ticker"):
            pieces.setdefault(str(ticker), []).append(part.drop(columns="ticker"))
    for ticker, parts in pieces.items():
        bars = pd.concat(parts).drop_duplicates("date", keep="last").set_index("date").sort_index()
        bars.index.name = "date"
        bars[COLUMNS].to_csv(out_dir / f"{ticker.upper()}_1Day.csv")
    return {"tickers": len(pieces), "rows": rows, "dir": str(out_dir)}


def coverage(membership: pd.Series, out_dir: Path = SHARADAR_DIR, first="2000-01-31", last="2015-12-31") -> pd.DataFrame:
    """Per month-end: members, and how many have a file with a bar within 5 days of that month-end."""
    from core.universe import members_on

    month_ends = pd.date_range(first, last, freq="ME")
    spans = {}
    for path in out_dir.glob("*_1Day.csv"):
        index = pd.read_csv(path, usecols=["date"], parse_dates=["date"])["date"]
        spans[path.name[:-len("_1Day.csv")]] = (index.min(), index.max())
    rows = []
    for when, members in zip(month_ends, members_on(membership, month_ends)):
        ok = sum(1 for t in members if t in spans and spans[t][0] <= when - pd.Timedelta(days=365)
                 and spans[t][1] >= when - pd.Timedelta(days=5))
        rows.append((when, len(members), ok))
    table = pd.DataFrame(rows, columns=["month_end", "members", "with_bars"]).set_index("month_end")
    table["share"] = table["with_bars"] / table["members"]
    return table


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    conv = sub.add_parser("convert")
    conv.add_argument("source", type=Path)
    sub.add_parser("coverage")
    args = parser.parse_args()
    if args.cmd == "convert":
        print(convert(args.source))
    else:
        from core.universe import load_membership

        table = coverage(load_membership())
        print(table.groupby(table.index.year)["share"].mean().round(3).to_string())
        print("overall", round(table["with_bars"].sum() / table["members"].sum(), 3))


if __name__ == "__main__":
    main()
