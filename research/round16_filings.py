"""Test 1 of round 16: hold the S&P 500 members whose latest 10-K/10-Q text changed least from the year-earlier filing.

    PYTHONPATH=. python research/round16_filings.py [--dry]

Needs data/round16/filings/ from research/round16_filings_data.py.
"""

import argparse
import json
import sys

import numpy as np
import pandas as pd

from core.backtest import _git_commit
from core.config import ROOT
from core.data import load_bars
from core.ledger import add_evidence, connect, set_status
from core.portfolio import month_ends, simulate
from core.universe import (FIRST_MONTH_END, LAST_MONTH_END, load_member_panel, load_membership, members_on,
                           month_end_members)
from research.round16_common import MEMO, register, title_of
from research.round16_filings_data import load_scores
from research.round5_verdicts import window_stats
from research.round6_scan import BAR, MIN_REBALANCES, WINDOWS, judge, lookup, placebo

OUT_DIR = ROOT / "backtests" / "round16_filings"
FIRST_DECISION = "2017-01-31"
FRACTION, MAX_AGE_DAYS = 0.2, 100
COSTS = {"primary": 5.0, "stress": 10.0}


def score_matrix(filings, column, index, columns, decisions):
    """Score per decision date and ticker: the latest filing accepted by 16:00 New York time of that date and within
    MAX_AGE_DAYS; a name whose latest filing has no year-earlier match is not scored."""
    out = pd.DataFrame(np.nan, index, columns)
    per_symbol = {s: g.sort_values("accepted") for s, g in filings.groupby("symbol") if s in out.columns}
    cutoffs = {d: (pd.Timestamp(d).tz_localize("America/New_York") + pd.Timedelta(hours=16)).tz_convert("UTC") for d in decisions}
    for s, g in per_symbol.items():
        acc = g["accepted"].dt.tz_convert("UTC").dt.tz_localize(None).to_numpy(dtype="datetime64[ns]")
        vals = g[column].to_numpy(dtype=float)
        for d in decisions:
            cut = np.datetime64(cutoffs[d].tz_localize(None))
            k = np.searchsorted(acc, cut, side="right") - 1
            if k >= 0 and (cut - acc[k]) <= np.timedelta64(MAX_AGE_DAYS, "D"):
                out.at[d, s] = vals[k]
    return out


def monthly_run(label, scores, close, close_ff, membership, decisions, bottom=False):
    index = close.index
    strategy = pd.DataFrame(np.nan, index, close.columns)
    bench = pd.DataFrame(np.nan, index, close.columns)
    detail = []
    for d, members in zip(decisions, members_on(membership, decisions)):
        priced = [t for t in sorted(members) if t in close.columns and pd.notna(close.at[d, t])]
        row = scores.loc[d, priced].dropna()
        ranked = list(row.index)
        strategy.loc[d] = 0.0
        bench.loc[d] = 0.0
        picks = []
        if len(ranked) >= 20:
            n = max(1, int(round(FRACTION * len(ranked))))
            order = row.sort_values(ascending=bottom, kind="mergesort")
            picks = sorted(order.index[:n])
            strategy.loc[d, picks] = 1.0 / n
            bench.loc[d, ranked] = 1.0 / len(ranked)
        detail.append({"date": d, "priced": ranked, "ranked": ranked if picks else [], "picks": picks, "off": not picks})
    runs = {name: simulate(close_ff, strategy, bps) for name, bps in COSTS.items()}
    benches = {name: simulate(close_ff, bench, bps) for name, bps in COSTS.items()}
    first_hold = index[index.get_loc(decisions[0]) + 1]
    cells = {}
    for w, (start, end) in WINDOWS.items():
        _, _, stats = window_stats(runs["primary"], benches["primary"], first_hold, start, end)
        stress = window_stats(runs["stress"], benches["stress"], first_hold, start, end)[2]["net_active"]
        gross, pct = placebo(detail, close_ff, index, start, end)
        n = sum(1 for d in detail if d["picks"] and pd.Timestamp(start) <= d["date"] and (end is None or d["date"] <= pd.Timestamp(end)))
        verdict, why = judge(w, n, stats, pct)
        if verdict == "supports" and stress <= 0:
            verdict, why = "contradicts", f"10 bps net active {stress:.2%} not above 0"
        cells[w] = {"verdict": verdict, "why": why, "rebalances": n, "net_active": stats["net_active"],
                    "information_ratio": stats["information_ratio"], "placebo": pct, "stress_net_active": stress,
                    "turnover": stats["annual_turnover"], "start": stats["start"], "end": stats["end"],
                    "cagr": stats["strategy"]["cagr"], "benchmark_cagr": stats["benchmark"]["cagr"],
                    "ranked_median": float(np.median([len(d["priced"]) for d in detail if d["picks"]] or [0]))}
    print(f"{label:30s}", "  ".join(
        f"{w} {c['net_active']:+6.1%} IR {c['information_ratio']:+5.2f} pl {c['placebo']:.2f} 10bp {c['stress_net_active']:+6.1%} "
        f"turn {c['turnover']:4.1f} n {c['rebalances']} ranked {c['ranked_median']:.0f}" for w, c in cells.items()), flush=True)
    return cells


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry", action="store_true")
    args = parser.parse_args()
    conn = connect()
    register(conn)
    membership = load_membership()
    index = load_bars("VTI").index
    wanted = sorted(month_end_members(membership, FIRST_MONTH_END, LAST_MONTH_END))
    close = load_member_panel(wanted, "close").reindex(index)
    close_ff = close.ffill()
    decisions = [d for d in index[month_ends(index)] if d >= pd.Timestamp(FIRST_DECISION)]
    filings = load_scores()
    errors = filings["error"].fillna("")
    ok = filings[(errors == "") & filings["words"].notna()]
    covered = sorted(set(ok["symbol"]) & set(close.columns))
    report = {"filings": int(len(filings)), "usable": int(len(ok)), "with_prior_year": int(ok["cosine"].notna().sum()),
              "symbols": int(filings["symbol"].nunique()), "covered_with_prices": len(covered),
              "errors": errors.value_counts().to_dict(), "first_decision": FIRST_DECISION}
    print("data check:", json.dumps(report), flush=True)
    close_c, close_ff_c = close[covered], close_ff[covered]
    scores = {"cosine": score_matrix(ok, "cosine", index, covered, decisions),
              "jaccard": score_matrix(ok, "jaccard", index, covered, decisions),
              "cosine_10k": score_matrix(ok[ok["form"] == "10-K"], "cosine", index, covered, decisions)}
    out = {"primary": monthly_run("cosine, 20% most similar (test)", scores["cosine"], close_c, close_ff_c, membership, decisions)}
    out["jaccard"] = monthly_run("report: jaccard", scores["jaccard"], close_c, close_ff_c, membership, decisions)
    out["tenk_only"] = monthly_run("report: 10-K only", scores["cosine_10k"], close_c, close_ff_c, membership, decisions)
    out["changers"] = monthly_run("report: 20% least similar", scores["cosine"], close_c, close_ff_c, membership, decisions, bottom=True)
    cells = out["primary"]
    vs = {c["verdict"] for c in cells.values()}
    status = "supported" if vs == {"supports"} else "rejected" if "contradicts" in vs else "testing"
    print("verdict:", status, json.dumps({w: [c["verdict"], c["why"]] for w, c in cells.items()}))
    if args.dry:
        return
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = pd.Timestamp.now("UTC").strftime("%Y%m%dT%H%M%SZ")
    path = OUT_DIR / f"filings_{stamp}.json"
    hid = lookup(conn)[title_of("filing_stable_q_m")]
    for w, c in cells.items():
        summary = (f"round16_filings filing_stable_q_m {w} {c['start']}..{c['end']}, 5 bps: {c['rebalances']} rebalances, net active "
                   f"{c['net_active']:.2%}/yr, IR {c['information_ratio']:.2f}, placebo {c['placebo']:.3f}, 10 bps {c['stress_net_active']:.2%}, "
                   f"turnover {c['turnover']:.1f}x/yr, median scored names {c['ranked_median']:.0f}; Jaccard {out['jaccard'][w]['net_active']:.2%}, "
                   f"10-K only {out['tenk_only'][w]['net_active']:.2%}, least-similar 20% {out['changers'][w]['net_active']:.2%}. "
                   f"{c['verdict']}: {c['why']}. Covered set is current S&P 500 members only; benchmark is the equal-weight scored names.")
        add_evidence(conn, hid, "backtest", summary, c["verdict"], ref=str(path.relative_to(ROOT)))
    set_status(conn, hid, status)
    path.write_text(json.dumps({"git_commit": _git_commit(), "run_at": stamp, "bar": BAR, "costs": COSTS, "data": report,
                                "results": out, "verdict": status}, indent=1, default=str) + "\n")
    conn.close()
    print(f"wrote {path.relative_to(ROOT)}")


if __name__ == "__main__":
    sys.exit(main())
