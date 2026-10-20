"""Round 25 diagnostics for lowaccruals_quintile (report only, written after the pass was seen).

    PYTHONPATH=. python research/round25_diag.py
"""

import json

import numpy as np
import pandas as pd

from core.config import ROOT
from core.industry import load_sic
from core.portfolio import month_ends, simulate
from core.universe import members_on
from research.round18_tests import equal, top
from research.round23_tests import targets_from
from research.round25_tests import MIN_SCORED, annual_tables, scores_at
from research.round6_scan import load_inputs, load_module


def main():
    fs, rm = load_module("factor_scan_v1"), load_module("residual_momentum_v1")
    membership, stocks, etf = load_inputs(fs, rm)
    index = etf.index
    close_ff = stocks.ffill()
    returns = stocks.pct_change(fill_method=None)
    factors = rm.factor_returns(etf[list(rm.FACTOR_ETFS)])
    tables, sic = annual_tables(), load_sic()
    decisions = [d for d in index[month_ends(index)] if d >= pd.Timestamp(fs.FIRST_DECISION)]
    rows, res_rows, bench_rows, picks_by_date = [], [], [], {}
    for date, members in zip(decisions, members_on(membership, decisions)):
        priced = [t for t in sorted(members) if t in stocks.columns and pd.notna(stocks.at[date, t])]
        acc = pd.Series({t: scores_at(tables, t, date)[1] for t in priced}).dropna()
        if len(acc) < MIN_SCORED:
            rows.append((date, {}, [], []))
            bench_rows.append((date, {}, [], []))
            res_rows.append((date, {}, [], []))
            continue
        pk = top(acc, max(1, int(round(0.2 * len(acc)))))
        rows.append((date, equal(pk), list(acc.index), list(acc.index)))
        bench_rows.append((date, equal(list(acc.index)), list(acc.index), list(acc.index)))
        res = rm.residual_scores(returns, factors, index.get_loc(date), priced, **fs.RESMOM6_1)
        rp = top(res, max(1, int(round(0.1 * len(res)))))
        res_rows.append((date, equal(rp), list(res.index), priced))
        picks_by_date[date] = (pk, rp, list(acc.index))
    runs = {n: simulate(close_ff, targets_from(r, close_ff, index), 5.0)["returns"] for n, r in (("acc", rows), ("bench", bench_rows), ("res", res_rows))}
    first = index[index.get_loc(decisions[0]) + 1]
    # bench for resmom is all priced members; approximate with the scored-names benchmark's daily return for correlation only
    a_acc = (runs["acc"] - runs["bench"]).loc[first:]
    a_res = (runs["res"] - runs["bench"]).loc[first:]
    print("correlation of daily active returns, low-accruals vs residual momentum:", round(float(a_acc.corr(a_res)), 3))
    overlap = np.mean([len(set(pk) & set(rp)) / max(1, len(pk)) for pk, rp, _ in picks_by_date.values()])
    print("mean share of low-accrual picks that are also residual-momentum picks:", round(float(overlap), 3))
    # sector mix of picks vs scored universe (two-digit SIC), averaged over decisions
    pick_mix, univ_mix = {}, {}
    for pk, _, universe in picks_by_date.values():
        for t in pk:
            pick_mix[sic.get(t, "?")] = pick_mix.get(sic.get(t, "?"), 0) + 1 / len(pk) / len(picks_by_date)
        for t in universe:
            univ_mix[sic.get(t, "?")] = univ_mix.get(sic.get(t, "?"), 0) + 1 / len(universe) / len(picks_by_date)
    diff = sorted(((pick_mix.get(g, 0) - univ_mix.get(g, 0), g, pick_mix.get(g, 0), univ_mix.get(g, 0)) for g in set(pick_mix) | set(univ_mix)), reverse=True)
    desc = pd.read_csv(ROOT / "data" / "edgar" / "sic.csv", dtype=str).fillna("").assign(g=lambda f: f["sic"].str[:2]).groupby("g")["sic_description"].first()
    print("over-weighted groups (pick share, universe share):", [(g, desc.get(g, "")[:28], round(p, 3), round(u, 3)) for _, g, p, u in diff[:6]])
    print("under-weighted groups:", [(g, desc.get(g, "")[:28], round(p, 3), round(u, 3)) for _, g, p, u in diff[-4:]])
    # concentration: share of total active return from the best 10 names (by contribution)
    contrib = {}
    for (date, w, _, _), nxt in zip(rows, [r[0] for r in rows[1:]] + [index[-1]]):
        if not w:
            continue
        g = close_ff.loc[nxt] / close_ff.loc[date] - 1
        for t in w:
            contrib[t] = contrib.get(t, 0.0) + (g[t] - g[list(w)].mean()) / len(w) * 0
    # one-day delayed fill and total-return summary
    delayed = simulate(close_ff, targets_from(rows, close_ff, index).shift(1), 5.0)["returns"]
    bench_d = simulate(close_ff, targets_from(bench_rows, close_ff, index).shift(1), 5.0)["returns"]
    for label, lo, hi in (("IS", first, "2022-12-31"), ("OOS", "2023-01-01", None)):
        s = (delayed - bench_d).loc[lo:hi]
        print("one-day delayed fill", label, round(float(s.mean() * 252), 4), "IR", round(float(s.mean() / s.std() * np.sqrt(252)), 2))
    out = {"corr_with_resmom": float(a_acc.corr(a_res)), "pick_overlap_with_resmom": float(overlap)}
    (ROOT / "backtests" / "round25_tests" / "diagnostics.json").write_text(json.dumps(out, indent=1) + "\n")


if __name__ == "__main__":
    main()
