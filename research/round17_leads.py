"""Round 17: is each round 16 lead a plateau or a spike among its neighbours? (research/r17-leads-2026-10-17.md)

    PYTHONPATH=. python research/round17_leads.py [--dry]
"""

import argparse
import json
import sys

import numpy as np
import pandas as pd

from core.backtest import _git_commit
from core.config import ROOT
from core.data import load_bars
from core.ledger import add_evidence, add_hypothesis, connect, set_status
from core.portfolio import month_ends, simulate
from core.universe import (FIRST_MONTH_END, LAST_MONTH_END, load_member_panel, load_membership, members_on,
                           month_end_members)
from research import round16_etf as etf
from research import round16_filings as fil
from research.round16_filings_data import load_scores
from research.round5_verdicts import holding_windows, in_window, window_stats
from research.round6_scan import load_module, lookup
from research.round6_scan import placebo as monthly_placebo
from research.round8_short_horizon import cleaned, dirty_index, placebo as daily_placebo
from research.round16_data import load_etfs

MEMO = "research/r17-leads-2026-10-17.md"
OUT_DIR = ROOT / "backtests" / "round17_leads"
WINDOWS = {"IS": ("2016-01-01", "2022-12-31"), "OOS": ("2023-01-01", None),
           "OOS_a": ("2023-01-01", "2024-12-31"), "OOS_b": ("2025-01-01", None)}
HORIZONS = [5, 8, 10, 12, 15, 20]
NEIGHBOURS = [8, 10, 12, 15]
HYP = {"rev10s_h3_band40_etf": "In the round 16 ETF set, the volatility-scaled 10-day reversal rule (and its neighbours at 8, 12 and 15 days) is a plateau, not a spike: OOS net active >= 2.0%/yr at 2 bps for each",
       "filing_changer_q_m": "Holding the least similar 10%/20%/33% of covered members by 10-K/10-Q text (cosine and Jaccard) is a plateau, not a spike: at least 4 of 6 variants have OOS net active >= 2.0%/yr"}


def register(conn):
    ids = lookup(conn)
    for rid, statement in HYP.items():
        title = f"Round 17: {rid}"
        if title not in ids:
            ids[title] = add_hypothesis(conn, title, statement + f" (see {MEMO}); pre-registered criteria in the memo.",
                                        rationale="Round 17: the two post-hoc leads of round 16, checked for robustness.",
                                        research_memo=MEMO, strategy="round17_leads.py")
    return {rid: ids[f"Round 17: {rid}"] for rid in HYP}


def cell(stats, stress, pct, n):
    return {"net_active": stats["net_active"], "information_ratio": stats["information_ratio"], "placebo": pct,
            "stress_net_active": stress, "turnover": stats["annual_turnover"], "decisions": n,
            "start": stats["start"], "end": stats["end"]}


def etf_variants():
    sh = load_module("short_horizon_v3")
    sh.FIRST_DECISION = etf.FIRST_DECISION
    rule = next(r for r in sh.RULES if r["id"] == "rev5_h3_band40_s")
    close, volume = load_etfs()
    index = close.index
    close_ff = close.ffill()
    dirty = dirty_index(index)
    elig = etf.eligibility(close, volume)
    ret = close.pct_change(fill_method=None)
    vol = ret.rolling(60, min_periods=50).std()
    decisions = sh.decision_dates(index, 3)
    monthly = [d for d in index[month_ends(index)] if d >= pd.Timestamp(etf.FIRST_DECISION)]
    members_fn = lambda dates: [frozenset(elig.columns[elig.loc[d].to_numpy()]) for d in dates]
    bt = etf.bench_targets(index, close.columns, elig, monthly)
    first_hold = index[index.get_loc(monthly[0]) + 1]
    bench = {n: cleaned(simulate(close_ff, bt, bps), dirty) for n, bps in (("p", 2.0), ("s", 5.0))}
    out = {}
    for k in HORIZONS:
        score = -(close / close.shift(k) - 1) / (vol * np.sqrt(k))
        targets, detail = sh.generate_targets(rule, close, score, None, decisions, members_fn)
        runs = {n: cleaned(simulate(close_ff, targets, bps), dirty) for n, bps in (("p", 2.0), ("s", 5.0))}
        wins = holding_windows(detail, index)
        cells = {}
        for w, (start, end) in WINDOWS.items():
            _, _, stats = window_stats(runs["p"], bench["p"], first_hold, start, end)
            stress = window_stats(runs["s"], bench["s"], first_hold, start, end)[2]["net_active"]
            _, pct = daily_placebo(detail, close_ff, index, start, end, dirty)
            n = sum(in_window(first, start, end) for _, first, _ in wins)
            cells[w] = cell(stats, stress, pct, n)
        out[k] = cells
        print(f"ETF k={k:2d} ", "  ".join(f"{w} {c['net_active']:+6.1%} IR {c['information_ratio']:+5.2f} pl {c['placebo']:.2f} 5bp {c['stress_net_active']:+6.1%}"
                                          for w, c in cells.items()), flush=True)
    return out


def etf_verdict(out):
    fails = []
    for k in NEIGHBOURS:
        o = out[k]["OOS"]
        if o["net_active"] < 0.02 or o["information_ratio"] < 0.3 or o["stress_net_active"] <= 0:
            fails.append(f"k={k}: OOS net active {o['net_active']:.2%}, IR {o['information_ratio']:.2f}, 5 bps {o['stress_net_active']:.2%} misses the bar")
    k10 = out[10]
    if k10["OOS"]["placebo"] < 0.95:
        fails.append(f"k=10 OOS placebo {k10['OOS']['placebo']:.3f} < 0.95")
    for h in ("OOS_a", "OOS_b"):
        if k10[h]["net_active"] <= 0:
            fails.append(f"k=10 {h} net active {k10[h]['net_active']:.2%} not above 0")
    return ("plateau", ["all neighbours and both halves hold"]) if not fails else ("spike", fails)


def filing_variants():
    membership = load_membership()
    index = load_bars("VTI").index
    wanted = sorted(month_end_members(membership, FIRST_MONTH_END, LAST_MONTH_END))
    close = load_member_panel(wanted, "close").reindex(index)
    close_ff = close.ffill()
    decisions = [d for d in index[month_ends(index)] if d >= pd.Timestamp(fil.FIRST_DECISION)]
    filings = load_scores()
    ok = filings[(filings["error"].fillna("") == "") & filings["words"].notna()]
    covered = sorted(set(ok["symbol"]) & set(close.columns))
    close_c, close_ff_c = close[covered], close_ff[covered]
    scores = {"cosine": fil.score_matrix(ok, "cosine", index, covered, decisions),
              "jaccard": fil.score_matrix(ok, "jaccard", index, covered, decisions)}
    out = {}
    for sim, matrix in scores.items():
        for frac in (0.1, 0.2, 0.33):
            fil.FRACTION = frac
            strategy = pd.DataFrame(np.nan, index, covered)
            bench = pd.DataFrame(np.nan, index, covered)
            detail = []
            for d, members in zip(decisions, members_on(membership, decisions)):
                priced = [t for t in sorted(members) if t in close_c.columns and pd.notna(close_c.at[d, t])]
                row = matrix.loc[d, priced].dropna()
                ranked = list(row.index)
                strategy.loc[d] = 0.0
                bench.loc[d] = 0.0
                picks = []
                if len(ranked) >= 20:
                    n = max(1, int(round(frac * len(ranked))))
                    picks = sorted(row.sort_values(ascending=True, kind="mergesort").index[:n])
                    strategy.loc[d, picks] = 1.0 / n
                    bench.loc[d, ranked] = 1.0 / len(ranked)
                detail.append({"date": d, "priced": ranked, "ranked": ranked if picks else [], "picks": picks, "off": not picks})
            runs = {n: simulate(close_ff_c, strategy, bps) for n, bps in (("p", 5.0), ("s", 10.0))}
            benches = {n: simulate(close_ff_c, bench, bps) for n, bps in (("p", 5.0), ("s", 10.0))}
            first_hold = index[index.get_loc(decisions[0]) + 1]
            cells = {}
            for w, (start, end) in WINDOWS.items():
                _, _, stats = window_stats(runs["p"], benches["p"], first_hold, start, end)
                stress = window_stats(runs["s"], benches["s"], first_hold, start, end)[2]["net_active"]
                _, pct = monthly_placebo(detail, close_ff_c, index, start, end)
                n_reb = sum(1 for d in detail if d["picks"] and pd.Timestamp(start) <= d["date"] and (end is None or d["date"] <= pd.Timestamp(end)))
                cells[w] = cell(stats, stress, pct, n_reb)
            key = f"{sim}_{int(round(frac * 100))}"
            out[key] = cells
            print(f"filings {key:10s}", "  ".join(f"{w} {c['net_active']:+6.1%} IR {c['information_ratio']:+5.2f} pl {c['placebo']:.2f} 10bp {c['stress_net_active']:+6.1%}"
                                                  for w, c in cells.items()), flush=True)
    return out


def filing_verdict(out):
    passing = []
    for key, cells in out.items():
        o = cells["OOS"]
        if (o["net_active"] >= 0.02 and o["information_ratio"] >= 0.3 and o["stress_net_active"] > 0
                and cells["OOS_a"]["net_active"] > 0 and cells["OOS_b"]["net_active"] > 0):
            passing.append(key)
    note = f"{len(passing)} of {len(out)} variants meet the plateau criteria ({', '.join(passing) or 'none'}; need 4)"
    return ("plateau" if len(passing) >= 4 else "spike", [note])


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry", action="store_true")
    args = parser.parse_args()
    conn = connect()
    ids = register(conn)
    e_out = etf_variants()
    f_out = filing_variants()
    verdicts = {"rev10s_h3_band40_etf": etf_verdict(e_out), "filing_changer_q_m": filing_verdict(f_out)}
    for rid, (v, why) in verdicts.items():
        print(rid, v, "; ".join(why))
    if args.dry:
        return
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = pd.Timestamp.now("UTC").strftime("%Y%m%dT%H%M%SZ")
    path = OUT_DIR / f"leads_{stamp}.json"
    ref = str(path.relative_to(ROOT))
    for rid, (v, why) in verdicts.items():
        if rid == "rev10s_h3_band40_etf":
            o, a, b = e_out[10]["OOS"], e_out[10]["OOS_a"], e_out[10]["OOS_b"]
            body = (f"k=10: OOS {o['net_active']:.2%}/yr (IR {o['information_ratio']:.2f}, placebo {o['placebo']:.3f}, 5 bps {o['stress_net_active']:.2%}), "
                    f"halves {a['net_active']:.2%} / {b['net_active']:.2%}; IS {e_out[10]['IS']['net_active']:.2%}; OOS by horizon "
                    + ", ".join(f"k={k} {e_out[k]['OOS']['net_active']:.1%}" for k in HORIZONS))
        else:
            body = "OOS net active by variant: " + ", ".join(f"{k} {c['OOS']['net_active']:.1%}" for k, c in f_out.items())
        summary = f"round17_leads {rid}: {v}. {'; '.join(why)}. {body}. Not an independent test: same data that suggested the lead."
        add_evidence(conn, ids[rid], "backtest", summary, "supports" if v == "plateau" else "contradicts", ref=ref)
        set_status(conn, ids[rid], "testing" if v == "plateau" else "rejected")
    path.write_text(json.dumps({"git_commit": _git_commit(), "run_at": stamp, "etf": e_out, "filings": f_out,
                                "verdicts": verdicts}, indent=1, default=str) + "\n")
    conn.close()
    print(f"wrote {path.relative_to(ROOT)}")


if __name__ == "__main__":
    sys.exit(main())
