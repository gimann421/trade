"""Round 18: the five highest-odds monthly ideas of research round 5 (research/r18-ranked-ideas-2026-10-18.md).

    PYTHONPATH=. python research/round18_tests.py --register
    PYTHONPATH=. python research/round18_tests.py [--dry]
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
from core.portfolio import month_ends, simulate
from core.universe import members_on
from research.round14_data import load_shares
from research.round18_data import load_eps
from research.round5_verdicts import holding_windows, in_window, window_stats
from research.round6_scan import BAR, MIN_REBALANCES, PLACEBO, load_inputs, load_module, lookup

MEMO = "research/r18-ranked-ideas-2026-10-18.md"
OUT_DIR = ROOT / "backtests" / "round18_tests"
WINDOWS = {"IS": ("2016-01-01", "2022-12-31"), "OOS": ("2023-01-01", None),
           "OOS_a": ("2023-01-01", "2024-12-31"), "OOS_b": ("2025-01-01", None)}
JUDGED = ("IS", "OOS")
MIN_SCORED = 20
SPLIT_CUT, SHARE_AGE, EPS_AGE = 0.37, 120, 100
HYP = {
    "resmom6_1_ivw_decile": "Residual momentum 6-1 top decile weighted by 1 / residual volatility passes the bar in both windows and beats the equal-weight parent's information ratio in both",
    "nsi_low_quintile": "Holding the 20% of covered members with the largest 12-month fall in cover-page shares passes the bar in both windows against the equal-weight scored names",
    "resmom6_1_lowiss_decile": "Residual momentum 6-1 among names with issuance at or below the median passes the bar in both windows and beats the same-set parent's net active in both",
    "indmom6_1_quintile": "Holding the 20% of covered members in the SIC two-digit groups with the best 6-1 return passes the bar in both windows against the equal-weight scored names",
    "sue_quintile": "Holding the 20% of covered members with the highest standardized unexpected earnings (SEC EPS) passes the bar in both windows against the equal-weight scored names",
}


def register(conn):
    ids = lookup(conn)
    for rid, statement in HYP.items():
        title = f"Round 18: {rid}"
        if title not in ids:
            ids[title] = add_hypothesis(conn, title, statement + f" (see {MEMO}); pre-registered criteria in the memo.",
                                        rationale="Round 18: top five of research round 5, ranked by pass odds.",
                                        research_memo=MEMO, strategy="round18_tests.py")
    return {rid: ids[f"Round 18: {rid}"] for rid in HYP}


# --- scores ------------------------------------------------------------------------------------

def residual_score_sd(rm, returns, factors, t_pos, tickers, start_lag, end_lag, min_valid):
    """As rm.residual_scores, but returns (score, residual sd) per ticker."""
    y, f = rm._window(returns[tickers], factors, t_pos, start_lag, end_lag)
    if y is None:
        return pd.DataFrame(columns=["score", "sd"])
    valid = y.notna()
    y, valid = y.loc[:, valid.sum() >= min_valid], valid.loc[:, valid.sum() >= min_valid]
    x = np.column_stack([np.ones(len(f)), f.to_numpy()])
    out = {}
    for ticker in y.columns:
        m = valid[ticker].to_numpy()
        yy, xx = y[ticker].to_numpy()[m], x[m]
        beta = np.linalg.lstsq(xx, yy, rcond=None)[0]
        resid = yy - xx[:, 1:] @ beta[1:]
        sd = resid.std(ddof=1)
        if sd > 0:
            out[ticker] = (resid.mean() / sd, sd)
    return pd.DataFrame(out, index=["score", "sd"]).T


def share_table():
    table = {}
    for symbol, g in load_shares().groupby("symbol"):
        g = g[g["shares"] > 0].drop_duplicates("filed", keep="last").sort_values("filed")
        table[symbol] = (g["filed"].to_numpy(dtype="datetime64[ns]"), g["shares"].to_numpy(dtype=float))
    return table


def issuance(table, ticker, date):
    """Minus the 12-month log change in shares (higher = shares fell), or NaN."""
    if ticker not in table:
        return np.nan
    filed, vals = table[ticker]
    d, past = np.datetime64(date), np.datetime64(date - pd.Timedelta(days=365))
    k = np.searchsorted(filed, d, side="left") - 1          # filed strictly before the decision day
    j = np.searchsorted(filed, past, side="right") - 1      # filed on or before a year earlier
    if k < 0 or j < 0 or (d - filed[k]) > np.timedelta64(SHARE_AGE, "D") or (past - filed[j]) > np.timedelta64(SHARE_AGE, "D"):
        return np.nan
    change = np.log(vals[k] / vals[j])
    return -change if abs(change) <= SPLIT_CUT else np.nan


def quarters(g):
    """First-filed quarterly EPS for one company: DataFrame(end, val, avail), fourth quarters derived from the year."""
    g = g.sort_values("filed")
    dur = (g["end"] - g["start"]).dt.days
    q = g[(dur >= 80) & (dur <= 100)].groupby(["start", "end"], as_index=False).first()
    y = g[(dur >= 350) & (dur <= 380)].groupby(["start", "end"], as_index=False).first()
    rows = [(r.end, r.val, r.filed) for r in q.itertuples()]
    for r in y.itertuples():
        if ((q["end"] - r.end).abs().dt.days <= 5).any():
            continue
        inside = q[(q["end"] > r.start) & (q["end"] < r.end - pd.Timedelta(days=5)) & (q["start"] >= r.start - pd.Timedelta(days=5))]
        if len(inside) == 3:
            rows.append((r.end, r.val - inside["val"].sum(), r.filed))
    out = pd.DataFrame(rows, columns=["end", "val", "avail"]).sort_values(["end", "avail"])
    keep, last = [], None
    for r in out.itertuples():
        if last is None or (r.end - last).days > 10:
            keep.append(r.Index)
            last = r.end
    return out.loc[keep].reset_index(drop=True)


def sue_table():
    eps = load_eps()
    eps = eps[(eps["unit"] == "USD/shares") & eps["start"].notna()]
    table = {}
    for symbol, g in eps.groupby("symbol"):
        q = quarters(g)
        diffs = []
        for k, r in q.iterrows():
            prev = q[(q["end"] >= r.end - pd.Timedelta(days=385)) & (q["end"] <= r.end - pd.Timedelta(days=345))]
            diffs.append(r.val - prev["val"].iloc[0] if len(prev) else np.nan)
        q["diff"] = diffs
        sue = []
        for k in range(len(q)):
            before = q["diff"].iloc[:k].dropna().iloc[-8:]
            sd = before.std(ddof=1) if len(before) >= 4 else np.nan
            sue.append(q["diff"].iloc[k] / sd if pd.notna(q["diff"].iloc[k]) and sd > 0 else np.nan)
        q["sue"] = sue
        table[symbol] = q
    return table


def sue_at(table, ticker, date):
    q = table.get(ticker)
    if q is None:
        return np.nan
    avail = q[q["avail"] < date]
    if avail.empty:
        return np.nan
    last = avail.loc[avail["end"].idxmax()]
    return last["sue"] if (date - last["avail"]).days <= EPS_AGE else np.nan


# --- engine ------------------------------------------------------------------------------------

def run_rule(rows, close_ff, index):
    """rows: per decision (date, picks->weight dict, ranked names, bench names). Returns cells per window."""
    strategy = pd.DataFrame(np.nan, index, close_ff.columns)
    bench = strategy.copy()
    detail = []
    for date, weights, ranked, bench_names in rows:
        strategy.loc[date] = 0.0
        bench.loc[date] = 0.0
        if weights:
            strategy.loc[date, list(weights)] = list(weights.values())
            bench.loc[date, bench_names] = 1.0 / len(bench_names)
        detail.append({"date": date, "weights": weights, "ranked": ranked if weights else [], "priced": bench_names})
    runs = {k: simulate(close_ff, strategy, bps) for k, bps in (("p", 5.0), ("s", 10.0))}
    benches = {k: simulate(close_ff, bench, bps) for k, bps in (("p", 5.0), ("s", 10.0))}
    first_hold = index[index.get_loc(detail[0]["date"]) + 1]
    windows = holding_windows(detail, index)
    cells = {}
    for w, (start, end) in WINDOWS.items():
        _, _, stats = window_stats(runs["p"], benches["p"], first_hold, start, end)
        stress = window_stats(runs["s"], benches["s"], first_hold, start, end)[2]["net_active"]
        n = sum(in_window(first, start, end) for (_, first, _), d in zip(windows, detail) if d["weights"])
        cells[w] = {"net_active": stats["net_active"], "information_ratio": stats["information_ratio"],
                    "placebo": placebo(detail, close_ff, index, start, end), "stress_net_active": stress,
                    "turnover": stats["annual_turnover"], "rebalances": n,
                    "median_picks": float(np.median([len(d["weights"]) for d in detail if d["weights"]] or [0])),
                    "median_ranked": float(np.median([len(d["ranked"]) for d in detail if d["weights"]] or [0])),
                    "start": stats["start"], "end": stats["end"]}
    return cells


def placebo(detail, close_ff, index, start, end):
    """round6_scan.placebo with the rule's weights: random names from the ranked set get the same weight vector."""
    rng = np.random.default_rng(PLACEBO["seed"])
    actual, draws = [], []
    for d, (date, first, last) in zip(detail, holding_windows(detail, index)):
        if not in_window(first, start, end):
            continue
        growth = close_ff.loc[last] / close_ff.loc[date] - 1
        if not d["weights"]:
            actual.append(0.0)
            draws.append(np.zeros(PLACEBO["n"]))
            continue
        b = growth[d["priced"]].mean()
        w = np.array(list(d["weights"].values()))
        a = float(growth[list(d["weights"])].to_numpy() @ w) - b
        actual.append(a)
        ranked = growth[d["ranked"]].to_numpy()
        idx = np.argsort(rng.random((PLACEBO["n"], len(ranked))), axis=1)[:, :len(w)]
        draws.append(ranked[idx] @ w - b)
    mean = float(np.mean(actual))
    return float((np.mean(np.array(draws), axis=0) < mean).mean())


def top(scores: pd.Series, n: int) -> list[str]:
    s = scores.dropna()
    return [t for t, _ in sorted(s.items(), key=lambda kv: (-kv[1], kv[0]))[:n]]


def equal(names):
    return {t: 1.0 / len(names) for t in names} if names else {}


def bar_fails(cells):
    fails = []
    for w in JUDGED:
        c = cells[w]
        if c["rebalances"] < MIN_REBALANCES[w]:
            fails.append(f"{w} only {c['rebalances']} rebalances")
        if c["net_active"] < BAR["net_active"]:
            fails.append(f"{w} net active {c['net_active']:.2%} < 2.0%")
        if c["information_ratio"] < BAR["information_ratio"]:
            fails.append(f"{w} IR {c['information_ratio']:.2f} < 0.3")
        if c["placebo"] < BAR["placebo"]:
            fails.append(f"{w} placebo {c['placebo']:.3f} < 0.95")
        if c["stress_net_active"] <= 0:
            fails.append(f"{w} 10 bps {c['stress_net_active']:.2%} not above 0")
    return fails


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
    returns = stocks.pct_change(fill_method=None)
    factors = rm.factor_returns(etf[list(rm.FACTOR_ETFS)])
    decisions = [d for d in index[month_ends(index)] if d >= pd.Timestamp(fs.FIRST_DECISION)]
    shares, sic, sue = share_table(), load_sic(), sue_table()
    mom61 = stocks.shift(21) / stocks.shift(126) - 1
    rows = {k: [] for k in ("parent_all", "ivw", "nsi", "nsi_high", "parent_iss", "lowiss", "ind", "ind_low", "sue", "sue_low")}
    cover, checks = [], []
    for date, members in zip(decisions, members_on(membership, decisions)):
        t_pos = index.get_loc(date)
        priced = [t for t in sorted(members) if t in stocks.columns and pd.notna(stocks.at[date, t])]
        res = residual_score_sd(rm, returns, factors, t_pos, priced, **fs.RESMOM6_1)
        ref = rm.residual_scores(returns, factors, t_pos, priced, **fs.RESMOM6_1)
        checks.append(float((res["score"].reindex(ref.index) - ref).abs().max()) if len(ref) else 0.0)
        # test 1: same picks as the shadow parent, weighted by 1 / residual sd
        picks = fs.pick(res["score"], fraction=0.1)
        inv = 1.0 / res.loc[picks, "sd"]
        rows["parent_all"].append((date, equal(picks), list(res.index), priced))
        rows["ivw"].append((date, (inv / inv.sum()).to_dict(), list(res.index), priced))
        # tests 2 and 3: issuance
        iss = pd.Series({t: issuance(shares, t, date) for t in priced}).dropna()
        n = len(iss)
        ok = n >= MIN_SCORED
        k20 = max(1, int(round(0.2 * n)))
        rows["nsi"].append((date, equal(top(iss, k20)) if ok else {}, list(iss.index), list(iss.index)))
        rows["nsi_high"].append((date, equal(top(-iss, k20)) if ok else {}, list(iss.index), list(iss.index)))
        both = sorted(set(iss.index) & set(res.index))
        rm_both = res.loc[both, "score"]
        ok3 = len(both) >= MIN_SCORED
        low = iss[both][iss[both] >= iss[both].median()].index
        rows["parent_iss"].append((date, equal(top(rm_both, max(1, int(round(0.1 * len(both)))))) if ok3 else {}, both, both))
        rows["lowiss"].append((date, equal(top(rm_both[low], max(1, int(round(0.2 * len(low)))))) if ok3 else {}, both, both))
        # test 4: industry momentum
        own = mom61.loc[date, [t for t in priced if t in sic.index]].dropna()
        grp = sic[own.index]
        size = grp.map(grp.value_counts())
        own = own[size >= 3]
        ind = own.groupby(sic[own.index]).transform("mean")
        k4 = max(1, int(round(0.2 * len(ind))))
        order = sorted(ind.index, key=lambda t: (-ind[t], -own[t], t))
        ok4 = len(ind) >= MIN_SCORED
        rows["ind"].append((date, equal(order[:k4]) if ok4 else {}, list(ind.index), list(ind.index)))
        rows["ind_low"].append((date, equal(order[::-1][:k4]) if ok4 else {}, list(ind.index), list(ind.index)))
        # test 5: SUE
        s = pd.Series({t: sue_at(sue, t, date) for t in priced}).dropna()
        k5 = max(1, int(round(0.2 * len(s))))
        ok5 = len(s) >= MIN_SCORED
        rows["sue"].append((date, equal(top(s, k5)) if ok5 else {}, list(s.index), list(s.index)))
        rows["sue_low"].append((date, equal(top(-s, k5)) if ok5 else {}, list(s.index), list(s.index)))
        cover.append({"date": str(date.date()), "priced": len(priced), "resmom": len(res), "issuance": n, "both": len(both),
                      "industry": len(ind), "groups": int(sic[ind.index].nunique()) if len(ind) else 0, "sue": len(s)})
    print("max |score - shadow score|:", max(checks))
    cov = pd.DataFrame(cover)
    print(cov.iloc[[0, 12, 24, 36, 48, 60, 72, -1]].to_string(index=False), flush=True)
    out = {}
    for k, r in rows.items():
        out[k] = run_rule(r, close_ff, index)
        print(f"{k:11s}", "  ".join(f"{w} {c['net_active']:+6.1%} IR {c['information_ratio']:+5.2f} pl {c['placebo']:.2f} 10bp {c['stress_net_active']:+6.1%} n {c['rebalances']}"
                                     for w, c in out[k].items()), flush=True)
    verdicts = {}
    f = bar_fails(out["ivw"]) + [f"{w} IR {out['ivw'][w]['information_ratio']:.2f} not above parent {out['parent_all'][w]['information_ratio']:.2f}"
                                 for w in JUDGED if out["ivw"][w]["information_ratio"] <= out["parent_all"][w]["information_ratio"]]
    verdicts["resmom6_1_ivw_decile"] = f
    verdicts["nsi_low_quintile"] = bar_fails(out["nsi"])
    verdicts["resmom6_1_lowiss_decile"] = bar_fails(out["lowiss"]) + [
        f"{w} net active {out['lowiss'][w]['net_active']:.2%} not above parent {out['parent_iss'][w]['net_active']:.2%}"
        for w in JUDGED if out["lowiss"][w]["net_active"] <= out["parent_iss"][w]["net_active"]]
    verdicts["indmom6_1_quintile"] = bar_fails(out["ind"])
    verdicts["sue_quintile"] = bar_fails(out["sue"])
    key = {"resmom6_1_ivw_decile": "ivw", "nsi_low_quintile": "nsi", "resmom6_1_lowiss_decile": "lowiss",
           "indmom6_1_quintile": "ind", "sue_quintile": "sue"}
    for rid, fails in verdicts.items():
        print(rid, "PASS" if not fails else "FAIL", "; ".join(fails))
    if args.dry:
        return
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = pd.Timestamp.now("UTC").strftime("%Y%m%dT%H%M%SZ")
    path = OUT_DIR / f"tests_{stamp}.json"
    ref = str(path.relative_to(ROOT))
    for rid, fails in verdicts.items():
        c = out[key[rid]]
        body = "; ".join(f"{w} {c[w]['net_active']:.2%}/yr (IR {c[w]['information_ratio']:.2f}, placebo {c[w]['placebo']:.3f}, 10 bps {c[w]['stress_net_active']:.2%})"
                         for w in JUDGED)
        summary = f"round18_tests {rid}: {'passes' if not fails else 'fails'}. {body}." + (f" Fails: {'; '.join(fails)}." if fails else "")
        add_evidence(conn, ids[rid], "backtest", summary, "supports" if not fails else "contradicts", ref=ref)
        set_status(conn, ids[rid], "supported" if not fails else "rejected")
    path.write_text(json.dumps({"git_commit": _git_commit(), "run_at": stamp, "coverage": cover, "results": out,
                                "verdicts": verdicts, "max_score_diff": max(checks)}, indent=1, default=str) + "\n")
    conn.close()
    print(f"wrote {ref}")


if __name__ == "__main__":
    sys.exit(main())
