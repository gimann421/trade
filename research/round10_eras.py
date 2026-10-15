"""Phase 3 of research/r10-robustness-and-eras-2026-10-15.md: does short-term reversal exist across eras?

    PYTHONPATH=. python research/round10_eras.py

C1: Ken French 49 industries (value-weighted, daily), top 5 by minus the 5-day return every 2nd day, keep while in top 15.
C2: nine sector funds (Yahoo), top 3 by minus the 5-day return every 2nd close, keep while in top 4.
Report-only: nothing is written to the ledger.
"""
import json
import sys

import numpy as np
import pandas as pd

from core.backtest import _git_commit
from core.config import ROOT
from core.longdata import load_french, load_long
from core.portfolio import simulate
from research.round5_verdicts import holding_windows, window_stats
from research.round6_scan import load_module
from research.round8_short_horizon import COSTS, cleaned, placebo

OUT = ROOT / "backtests" / "round10_eras"
SECTORS = "XLB XLE XLF XLI XLK XLP XLU XLV XLY".split()
FAMILIES = {
    "C1_industries49": {"fraction": 5 / 49, "band": 15 / 49,
                        "eras": {"1927-1949": ("1927-01-01", "1949-12-31"), "1950-1974": ("1950-01-01", "1974-12-31"),
                                 "1975-1999": ("1975-01-01", "1999-12-31"), "2000-2015": ("2000-01-01", "2015-12-31"),
                                 "2016-end": ("2016-01-01", None)}},
    "C2_sector_funds": {"fraction": 1 / 3, "band": 4 / 9,
                        "eras": {"1999-2007": ("1999-01-01", "2007-12-31"), "2008-2015": ("2008-01-01", "2015-12-31"),
                                 "2016-end": ("2016-01-01", None)}},
}
DIRTY = ("2020-03-09", "2020-03-20")


def run_family(name, price, spec, sh, dirty_all):
    index = price.index
    ret5 = price / price.shift(5) - 1
    # ranked only if all five returns exist: price was built with fillna(0), so use the raw availability mask
    score = -ret5.where(spec["avail"].rolling(6).min() == 1)
    rule = {"kind": "band", "fraction": spec["fraction"], "band": spec["band"]}
    decisions = list(index[10::2])
    held, targets = [], pd.DataFrame(np.nan, index, price.columns)
    bench_t = pd.DataFrame(np.nan, index, price.columns)
    detail = []
    for date in decisions:
        row = score.loc[date].dropna()
        avail = list(price.columns[spec["avail"].loc[date].astype(bool)])
        picks = sh.select(rule, row, held)
        targets.loc[date] = 0.0
        bench_t.loc[date] = 0.0
        if picks:
            targets.loc[date, picks] = 1 / len(picks)
        if avail:
            bench_t.loc[date, avail] = 1 / len(avail)
        held = picks
        detail.append({"date": date, "priced": avail, "ranked": list(row.index), "picks": picks})
    dirty = index[(index >= pd.Timestamp(DIRTY[0])) & (index <= pd.Timestamp(DIRTY[1]))] if dirty_all else index[:0]
    runs = {k: cleaned(simulate(price, targets, bps), dirty) for k, bps in (("p", COSTS["primary"]),)}
    bench = cleaned(simulate(price, bench_t, COSTS["primary"]), dirty)
    first = index[index.get_loc(detail[0]["date"]) + 1]
    out = {}
    for era, (s, e) in spec["eras"].items():
        _, _, st = window_stats(runs["p"], bench, first, s, e)
        extra = st["annual_turnover"] - st["benchmark_annual_turnover"]
        gross = st["net_active"] + extra * COSTS["primary"] / 1e4
        _, pct = placebo(detail, price, index, s, e, dirty)
        present = st["net_active"] > 0 and pct >= 0.95
        out[era] = {"net_active": st["net_active"], "gross_active": gross, "information_ratio": st["information_ratio"],
                    "placebo": pct, "turnover": st["annual_turnover"], "present": bool(present),
                    "start": st["start"], "end": st["end"]}
        print(f"{name:16s} {era:10s} {st['start']}..{st['end']} net {st['net_active']:+6.1%} gross {gross:+6.1%} "
              f"IR {st['information_ratio']:+5.2f} placebo {pct:.2f} turn {st['annual_turnover']:4.0f} present={present}", flush=True)
    out["broadly_present"] = sum(v["present"] for k, v in out.items() if k != "broadly_present") >= (4 if name.startswith("C1") else 3)
    print(f"{name}: broadly present = {out['broadly_present']}")
    return out


def main():
    sh = load_module("short_horizon_v3")
    results = {}
    ind = load_french("ind49_daily")
    ind = ind.apply(pd.to_numeric, errors="coerce")
    ind.index = pd.DatetimeIndex(pd.to_datetime(ind.index))
    ind = ind.loc[ind.index >= "1926-07-01"]
    if ind.abs().max().max() > 1.5:   # percent units
        ind = ind / 100.0
    ind = ind.where(ind > -0.99)
    avail = ind.notna().astype(int)
    price = (1 + ind.fillna(0.0)).cumprod()
    results["C1_industries49"] = run_family("C1_industries49", price, dict(FAMILIES["C1_industries49"], avail=avail), sh, False)

    closes = pd.DataFrame({s: load_long(s)["close"] for s in SECTORS}).dropna()
    closes.index = pd.DatetimeIndex(closes.index)
    avail = closes.notna().astype(int)
    results["C2_sector_funds"] = run_family("C2_sector_funds", closes, dict(FAMILIES["C2_sector_funds"], avail=avail), sh, True)
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "eras.json"
    path.write_text(json.dumps({"git_commit": _git_commit(), "results": results}, indent=1, default=str) + "\n")
    print(f"wrote {path.relative_to(ROOT)}")


if __name__ == "__main__":
    sys.exit(main())
