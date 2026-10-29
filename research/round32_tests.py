"""Round 32: combining low accruals and R&D intensity (research/r32-combine-passes-2026-10-29.md).

    PYTHONPATH=. python research/round32_tests.py --register
    PYTHONPATH=. python research/round32_tests.py [--dry]
"""

import argparse
import json
import sys

import numpy as np
import pandas as pd

from core.backtest import _git_commit
from core.config import ROOT
from core.industry import load_sic
from core.ledger import add_evidence, add_hypothesis, connect, set_status
from core.portfolio import month_ends
from core.universe import members_on
from research import round28_data
from research.round18_tests import JUDGED, bar_fails, equal, run_rule, top
from research.round25_data import load_facts
from research.round25_tests import annual_tables, scores_at
from research.round26_tests import active_series
from research.round28_tests import scores as rnd_scores, tables_from
from research.round6_scan import load_inputs, load_module, lookup

MEMO = "research/r32-combine-passes-2026-10-29.md"
OUT_DIR = ROOT / "backtests" / "round32_tests"
MIN_SCORED = 20
HYP = {
    "combo_rank_quintile": "Holding the 20% with the best average rank of low accruals and R&D intensity passes the bar in both windows and beats both parents",
    "rnd_in_lowacc_half": "Holding the top R&D intensity names within the lower-accruals half passes the bar in both windows and beats both parents",
    "lowacc_in_rnd_names": "Holding the 20% lowest accruals among R&D-reporting names passes the bar in both windows and beats both parents",
}
KEY = {"combo_rank_quintile": "combo", "rnd_in_lowacc_half": "cond", "lowacc_in_rnd_names": "accrnd"}


def register(conn):
    ids = lookup(conn)
    for rid, statement in HYP.items():
        title = f"Round 32: {rid}"
        if title not in ids:
            ids[title] = add_hypothesis(conn, title, statement + f" (see {MEMO}); pre-registered criteria in the memo.",
                                        rationale="Round 32: combinations of the two passes, keep testing until more pass.",
                                        research_memo=MEMO, strategy="round32_tests.py")
    return {rid: ids[f"Round 32: {rid}"] for rid in HYP}


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--register", action="store_true")
    parser.add_argument("--dry", action="store_true")
    args = parser.parse_args()
    conn = connect()
    ids = register(conn)
    if args.register:
        print(f"registered {ids}")
        return
    fs, rm = load_module("factor_scan_v1"), load_module("residual_momentum_v1")
    membership, stocks, etf = load_inputs(fs, rm)
    index = etf.index
    close_ff = stocks.ffill()
    tables = tables_from(pd.concat([load_facts(), round28_data.load_facts()], ignore_index=True))
    acc_tables = annual_tables()
    sic = load_sic().astype(int)
    techhealth = set(sic.index[sic.isin([28, 35, 36, 37, 38, 73])])
    decisions = [d for d in index[month_ends(index)] if d >= pd.Timestamp(fs.FIRST_DECISION)]
    names = ["combo", "cond", "accrnd", "parent_rnd", "parent_acc", "combo_low"]
    rows = {k: [] for k in names}
    share = {k: [] for k in ("combo", "cond", "accrnd")}
    cover = []
    for date, members in zip(decisions, members_on(membership, decisions)):
        priced = [t for t in sorted(members) if t in stocks.columns and pd.notna(stocks.at[date, t])]
        df = pd.DataFrame({"rnd": {t: rnd_scores(tables, t, date)["rnd"] for t in priced},
                           "acc": {t: scores_at(acc_tables, t, date)[1] for t in priced}}).dropna()
        ok = len(df) >= MIN_SCORED
        names_all = list(df.index)
        k = lambda n: max(1, int(round(0.2 * n)))
        def add(key, picks):
            rows[key].append((date, equal(picks) if ok and picks else {}, names_all, names_all))
            if key in share and ok and picks:
                share[key].append(float(np.mean([t in techhealth for t in picks])))
        if ok:
            combo = df.rank(pct=True).mean(axis=1)
            add("combo", top(combo, k(len(df))))
            add("combo_low", top(-combo, k(len(df))))
            half = df["acc"].nlargest(len(df) // 2).index
            add("cond", top(df.loc[half, "rnd"], max(1, int(round(0.2 * len(df))))))
            add("accrnd", top(df["acc"], k(len(df))))
            add("parent_rnd", top(df["rnd"], k(len(df))))
            add("parent_acc", top(df["acc"], k(len(df))))
        else:
            for key in names:
                rows[key].append((date, {}, [], []))
        cover.append({"date": str(date.date()), "priced": len(priced), "both": len(df)})
    print(pd.DataFrame(cover).iloc[[0, 12, 36, 60, 84, -1]].to_string(index=False), flush=True)
    out, corr = {}, {}
    pr, pa = active_series(rows["parent_rnd"], close_ff), active_series(rows["parent_acc"], close_ff)
    for name, r in rows.items():
        out[name] = run_rule(r, close_ff, index)
        if name in KEY.values():
            a = active_series(r, close_ff)
            corr[name] = {"rnd": float(a.corr(pr)), "acc": float(a.corr(pa))}
        print(f"{name:11s}", "  ".join(f"{w} {c['net_active']:+6.1%} IR {c['information_ratio']:+5.2f} pl {c['placebo']:.2f} 10bp {c['stress_net_active']:+6.1%} n {c['rebalances']}"
                                       for w, c in out[name].items() if w in JUDGED), flush=True)
    print("corr with parents:", {k: {a: round(b, 2) for a, b in v.items()} for k, v in corr.items()})
    print("mean tech/health share:", {k: round(float(np.mean(v)), 2) if v else None for k, v in share.items()})
    verdicts = {}
    for rid, key in KEY.items():
        fails = bar_fails(out[key])
        for w in JUDGED:
            best = max(out["parent_rnd"][w]["information_ratio"], out["parent_acc"][w]["information_ratio"])
            if not out[key][w]["information_ratio"] > best:
                fails.append(f"{w} IR {out[key][w]['information_ratio']:.2f} not above the better parent's {best:.2f}")
        verdicts[rid] = fails
        print(rid, "PASS" if not fails else "FAIL", "; ".join(fails))
    if args.dry:
        return
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = pd.Timestamp.now("UTC").strftime("%Y%m%dT%H%M%SZ")
    path = OUT_DIR / f"tests_{stamp}.json"
    ref = str(path.relative_to(ROOT))
    for rid, fails in verdicts.items():
        c = out[KEY[rid]]
        body = "; ".join(f"{w} {c[w]['net_active']:.2%}/yr (IR {c[w]['information_ratio']:.2f}, placebo {c[w]['placebo']:.3f}, 10 bps {c[w]['stress_net_active']:.2%})" for w in JUDGED)
        add_evidence(conn, ids[rid], "backtest", f"round32_tests {rid}: {'passes' if not fails else 'fails'}. {body}." +
                     (f" Fails: {'; '.join(fails)}." if fails else ""), "supports" if not fails else "contradicts", ref=ref)
        set_status(conn, ids[rid], "supported" if not fails else "rejected")
    path.write_text(json.dumps({"git_commit": _git_commit(), "run_at": stamp, "coverage": cover, "results": out, "corr_with_parents": corr,
                                "verdicts": verdicts}, indent=1, default=str) + "\n")
    conn.close()
    print(f"wrote {ref}")


if __name__ == "__main__":
    sys.exit(main())
