"""Free long-history data for tests on years before Alpaca's 2016 start: Yahoo ETF prices, Ken French
factor and industry returns, and FRED series. Everything lands in data/long/ (gitignored).

    python -m core.longdata etf        # Yahoo daily bars for the ETFs the earlier rounds used
    python -m core.longdata french     # Fama-French factors, momentum, reversal, 49 industries (daily, from 1926)
    python -m core.longdata fred       # rates, spreads, VIX
    python -m core.longdata check      # compare Yahoo with Alpaca where both exist (2016 onward)

Yahoo's chart endpoint is unofficial and may change or throttle. It has no history for delisted
stocks and can serve a different company under a reused ticker, so it is used for ETFs only.
Yahoo gives dividend-adjusted closes; the open, high and low are scaled by the same factor so the
files match the layout and adjustment convention of Alpaca's bars (core.data.load_bars).
"""

import argparse
import io
import json
import time
import urllib.request
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from core.data import COLUMNS, DATA_DIR, load_bars

LONG_DIR = DATA_DIR / "long"
FRENCH_DIR = LONG_DIR / "french"
FRED_DIR = LONG_DIR / "fred"
UA = {"User-Agent": "Mozilla/5.0 (research script)"}
YAHOO_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?period1=0&period2={now}&interval=1d&events=div%2Csplit"
ETFS = ("AGG BIL DBC EDV EEM EFA GLD HYG IEF IEI IWB IWD IWF IWM LQD QQQ SHY SPTL SPY TLH TLT VEA VGIT VGLT VNQ VTI "
        "XLB XLE XLF XLI XLK XLP XLU XLV XLY ZROZ").split()
FRENCH_FILES = {
    "ff3_daily": "F-F_Research_Data_Factors_daily_CSV.zip",
    "ff5_daily": "F-F_Research_Data_5_Factors_2x3_daily_CSV.zip",
    "mom_daily": "F-F_Momentum_Factor_daily_CSV.zip",
    "str_daily": "F-F_ST_Reversal_Factor_daily_CSV.zip",
    "ind49_daily": "49_Industry_Portfolios_daily_CSV.zip",
}
FRENCH_BASE = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
FRED_SERIES = ("DGS10", "DGS2", "DGS3MO", "DTB3", "DFF", "T10Y2Y", "BAA10Y", "BAMLH0A0HYM2", "VIXCLS")


def _get(url: str, timeout: int = 60, headers: dict | None = UA) -> bytes:
    return urllib.request.urlopen(urllib.request.Request(url, headers=headers or {}), timeout=timeout).read()


# --- Yahoo ETF bars -----------------------------------------------------------------------------

def parse_yahoo(payload: dict) -> pd.DataFrame:
    """Chart payload -> adjusted open/high/low/close/volume indexed by New York date."""
    result = payload["chart"]["result"][0]
    index = pd.to_datetime(result["timestamp"], unit="s", utc=True).tz_convert("America/New_York").tz_localize(None).normalize()
    quote = result["indicators"]["quote"][0]
    frame = pd.DataFrame({k: quote[k] for k in ("open", "high", "low", "close", "volume")}, index=index)
    frame["adj"] = result["indicators"]["adjclose"][0]["adjclose"]
    frame = frame.dropna(subset=["close", "adj"])
    factor = frame["adj"] / frame["close"]
    for column in ("open", "high", "low", "close"):
        frame[column] = frame[column] * factor
    frame = frame[COLUMNS]
    frame.index.name = "date"
    return frame[~frame.index.duplicated(keep="last")].sort_index()


def fetch_yahoo(symbol: str) -> pd.DataFrame:
    payload = json.loads(_get(YAHOO_URL.format(symbol=symbol, now=int(time.time()))))
    if not payload["chart"]["result"]:
        raise ValueError(f"no Yahoo data for {symbol}")
    return parse_yahoo(payload)


def load_long(symbol: str) -> pd.DataFrame:
    return load_bars(symbol, LONG_DIR)


def download_etfs(symbols=ETFS, pause: float = 0.6) -> dict:
    from core.paper_runner import last_completed_session
    last = last_completed_session()
    LONG_DIR.mkdir(parents=True, exist_ok=True)
    summary = {}
    for symbol in symbols:
        try:
            frame = fetch_yahoo(symbol)
            frame = frame[frame.index <= last]
            frame.to_csv(LONG_DIR / f"{symbol}_1Day.csv")
            summary[symbol] = {"first": str(frame.index[0].date()), "last": str(frame.index[-1].date()), "bars": len(frame)}
        except Exception as exc:  # report and continue
            summary[symbol] = {"error": f"{type(exc).__name__}: {exc}"[:160]}
        time.sleep(pause)
    (LONG_DIR / "etf_manifest.json").write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n")
    return summary


# --- Ken French ---------------------------------------------------------------------------------

def parse_french(text: str) -> dict[str, pd.DataFrame]:
    """Every table of daily returns in a French CSV, as decimals, keyed by '<title line>#<n>'."""
    lines = text.splitlines()
    tables, i = {}, 0
    while i < len(lines):
        first = lines[i].split(",")[0].strip()
        if not (first.isdigit() and len(first) == 8):
            i += 1
            continue
        above = [l for l in lines[:i] if l.strip()]
        header, title = above[-1], (above[-2].strip() if len(above) > 1 else "table")
        columns = [c.strip() for c in header.split(",")][1:]
        rows = []
        while i < len(lines) and lines[i].split(",")[0].strip().isdigit():
            rows.append(lines[i].split(","))
            i += 1
        frame = pd.DataFrame([[float(v) for v in r[1:1 + len(columns)]] for r in rows], columns=columns,
                             index=pd.to_datetime([r[0].strip() for r in rows], format="%Y%m%d"))
        frame = frame.where(~frame.isin([-99.99, -999.0]))
        frame.index.name = "date"
        tables[f"{title}#{len(tables)}"] = frame / 100.0
    return tables


def download_french() -> dict:
    FRENCH_DIR.mkdir(parents=True, exist_ok=True)
    summary = {}
    for key, name in FRENCH_FILES.items():
        archive = zipfile.ZipFile(io.BytesIO(_get(FRENCH_BASE + name)))
        text = archive.read(archive.namelist()[0]).decode("latin1")
        for n, (title, frame) in enumerate(parse_french(text).items()):
            suffix = "" if n == 0 else f"_t{n}"
            frame.to_csv(FRENCH_DIR / f"{key}{suffix}.csv")
            summary[f"{key}{suffix}"] = {"title": title, "first": str(frame.index[0].date()), "last": str(frame.index[-1].date()),
                                          "rows": len(frame), "columns": list(frame.columns)[:6]}
    (FRENCH_DIR / "manifest.json").write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n")
    return summary


def load_french(key: str) -> pd.DataFrame:
    return pd.read_csv(FRENCH_DIR / f"{key}.csv", index_col="date", parse_dates=True)


# --- FRED ---------------------------------------------------------------------------------------

def parse_fred(text: str, series: str) -> pd.Series:
    frame = pd.read_csv(io.StringIO(text), na_values=["."])
    out = pd.Series(frame.iloc[:, 1].astype(float).to_numpy(), pd.to_datetime(frame.iloc[:, 0]), name=series)
    out.index.name = "date"
    return out.dropna()


def download_fred(series=FRED_SERIES) -> dict:
    FRED_DIR.mkdir(parents=True, exist_ok=True)
    summary = {}
    for name in series:
        try:
            s = parse_fred(_get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={name}", headers=None).decode(), name)
            s.to_csv(FRED_DIR / f"{name}.csv")
            summary[name] = {"first": str(s.index[0].date()), "last": str(s.index[-1].date()), "rows": len(s)}
        except Exception as exc:
            summary[name] = {"error": f"{type(exc).__name__}: {exc}"[:160]}
        time.sleep(0.3)
    (FRED_DIR / "manifest.json").write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n")
    return summary


# --- Yahoo versus Alpaca ------------------------------------------------------------------------

def compare_with_alpaca(symbols=ETFS, start="2016-01-01") -> pd.DataFrame:
    """Per symbol, on the dates both have a bar: share of days whose adjusted returns agree within 1 bp,
    the largest disagreement, and the gap between the two cumulative adjusted growths."""
    rows = []
    for symbol in symbols:
        try:
            a, y = load_bars(symbol)["close"], load_long(symbol)["close"]
        except FileNotFoundError:
            continue
        both = pd.concat([a.rename("alpaca"), y.rename("yahoo")], axis=1).loc[start:].dropna()
        ra, ry = both["alpaca"].pct_change().dropna(), both["yahoo"].pct_change().dropna()
        diff = (ra - ry).abs()
        rows.append({"symbol": symbol, "days": len(ra), "within_1bp": float((diff < 1e-4).mean()), "max_abs_diff": float(diff.max()),
                     "growth_gap": float((both["yahoo"].iloc[-1] / both["yahoo"].iloc[0]) / (both["alpaca"].iloc[-1] / both["alpaca"].iloc[0]) - 1),
                     "missing_vs_alpaca": int(len(a.loc[start:].index.difference(y.index))),
                     "extra_vs_alpaca": int(len(y.loc[start:].index.difference(a.index)))})
    return pd.DataFrame(rows).set_index("symbol")


# --- the older era (everything up to 2015-12-31) -----------------------------------------------

OLD_END = "2015-12-31"


def synthetic_bil(first_real: pd.Timestamp, first_real_close: float) -> pd.DataFrame:
    """BIL before its 2007-05-30 launch: the French daily one-month T-bill return compounded, scaled so
    the series joins the real fund's adjusted close on its first day. Flat bars, zero volume."""
    rf_all = load_french("ff3_daily")["RF"].dropna()
    rf = rf_all[rf_all.index < first_real]
    growth = (1 + rf).cumprod()
    launch_day_return = float(rf_all.get(first_real, 0.0))
    anchor = first_real_close / (1 + launch_day_return)  # level on the last day before launch
    close = growth / growth.iloc[-1] * anchor
    frame = pd.DataFrame({"open": close, "high": close, "low": close, "close": close, "volume": 0.0})
    frame.index.name = "date"
    return frame


def old_bars(symbol: str, end: str = OLD_END) -> pd.DataFrame:
    """Yahoo bars for the older-era tests, cut at `end` so nothing after it can be seen. BIL is extended
    back before its launch with synthetic_bil (documented in research/r7-older-era-2026-10-14.md)."""
    bars = load_long(symbol)
    if symbol == "BIL":
        head = synthetic_bil(bars.index[0], float(bars["close"].iloc[0]))
        bars = pd.concat([head, bars])
    return bars.loc[:end]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("what", choices=["etf", "french", "fred", "check", "all"])
    args = parser.parse_args()
    if args.what in ("etf", "all"):
        for k, v in download_etfs().items():
            print(k, v)
    if args.what in ("french", "all"):
        for k, v in download_french().items():
            print(k, v)
    if args.what in ("fred", "all"):
        for k, v in download_fred().items():
            print(k, v)
    if args.what in ("check", "all"):
        pd.set_option("display.width", 200)
        print(compare_with_alpaca().round(5).to_string())


if __name__ == "__main__":
    main()
