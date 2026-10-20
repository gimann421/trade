"""Round 23: volatility-scaled momentum tilt, stock-specific reversal propensity, illiquidity, small dollar volume, January pause
(research/r23-tilt-scaling-reversal-propensity-liquidity-2026-10-20.md).

    PYTHONPATH=. python research/round23_tests.py --register
    PYTHONPATH=. python research/round23_tests.py [--dry]
"""

import argparse
import json
import sys

import numpy as np
import pandas as pd

from core.backtest import _git_commit
from core.config import ROOT
from core.intraday import sample_tickers
from core.ledger import add_evidence, add_hypothesis, connect, set_status
from core.portfolio import month_ends, simulate
from core.universe import load_member_panel, members_on
from research.round5_verdicts import holding_windows, in_window, window_stats
from research.round6_scan import BAR, MIN_REBALANCES, PLACEBO, load_inputs, load_module, lookup
from research.round8_short_horizon import dirty_index
from research.round18_tests import JUDGED, WINDOWS, bar_fails, equal, run_rule, top
from research.round21_tests import member_mask
from research.round22_tests import daily_eval, daily_fails as _unused  # noqa: F401

MEMO = "research/r23-tilt-scaling-reversal-propensity-liquidity-2026-10-20.md"
OUT_DIR = ROOT / "backtests" / "round23_tests"
MIN_DECISIONS = {"IS": 160, "OOS": 100}
HYP = {
    "resmom_volscaled_tilt": "Residual momentum picks blended with the equal-weight members by a volatility scale (own active-return volatility) passes the bar in both windows and beats the parent's information ratio",
    "rev5_acfneg_h3_band40_s": "The band reversal rule ranked only among names with below-median own return autocorrelation passes the bar in both windows on both screens and beats the plain parent",
    "illiq_high_quintile": "Holding the 20% most illiquid (Amihud) S&P 500 members passes the bar in both windows",
    "lowdv_quintile": "Holding the 20% of members with the lowest dollar volume passes the bar in both windows",
    "resmom_nojan": "Residual momentum with the equal-weight members held for the January period passes the bar in both windows and beats the parent's net active",
}


def register(conn):
    ids = lookup(conn)
    for rid, statement in HYP.items():
        title = f"Round 23: {rid}"
        if title not in ids:
            ids[title] = add_hypothesis(conn, title, statement + f" (see {MEMO}); pre-registered criteria in the memo.",
                                        rationale="Round 23: thread-chosen ideas, keep testing until one passes.",
                                        research_memo=MEMO, strategy="round23_tests.py")
    return {rid: ids[f"Round 23: {rid}"] for rid in HYP}


def targets_from(rows, close_ff, index):
    strategy = pd.DataFrame(np.nan, index, close_ff.columns)
    for date, weights, ranked, priced in rows:
        strategy.loc[date] = 0.0
        if weights:
            strategy.loc[date, list(weights)] = list(weights.values())
    return strategy


def run_rule_s(rows, close_ff, index):
    """rows: (date, picks weights, ranked, priced, s). Weights = s * picks + (1 - s) * equal-weight priced; benchmark equal-weight priced."""
    strategy = pd.DataFrame(np.nan, index, close_ff.columns)
    bench = strategy.copy()
    detail = []
    for date, picks, ranked, priced, s in rows:
        strategy.loc[date] = 0.0
        bench.loc[date] = 0.0
        bench.loc[date, priced] = 1.0 / len(priced)
        strategy.loc[date, priced] = (1 - s) / len(priced)
        for t, w in picks.items():
            strategy.loc[date, t] += s * w
        detail.append({"date": date, "weights": picks, "ranked": ranked, "priced": priced, "s": s})
    runs = {k: simulate(close_ff, strategy, bps) for k, bps in (("p", 5.0), ("s", 10.0))}
    benches = {k: simulate(close_ff, bench, bps) for k, bps in (("p", 5.0), ("s", 10.0))}
    first_hold = index[index.get_loc(detail[0]["date"]) + 1]
    windows = holding_windows(detail, index)
    cells = {}
    for w, (start, end) in WINDOWS.items():
        _, _, stats = window_stats(runs["p"], benches["p"], first_hold, start, end)
        stress = window_stats(runs["s"], benches["s"], first_hold, start, end)[2]["net_active"]
        rng = np.random.default_rng(PLACEBO["seed"])
        actual, draws = [], []
        for d, (date, first, last) in zip(detail, windows):
            if not in_window(first, start, end):
                continue
            growth = close_ff.loc[last] / close_ff.loc[date] - 1
            b = growth[d["priced"]].mean()
            k = len(d["weights"])
            actual.append(d["s"] * (growth[list(d["weights"])].mean() - b))
            ranked = growth[d["ranked"]].to_numpy()
            idx = np.argsort(rng.random((PLACEBO["n"], len(ranked))), axis=1)[:, :k]
            draws.append(d["s"] * (ranked[idx].mean(axis=1) - b))
        mean = float(np.mean(actual))
        n = sum(in_window(first, start, end) for (_, first, _) in windows)
        cells[w] = {"net_active": stats["net_active"], "information_ratio": stats["information_ratio"],
                    "placebo": float((np.mean(np.array(draws), axis=0) < mean).mean()), "stress_net_active": stress,
                    "turnover": stats["annual_turnover"], "rebalances": n, "mean_s": float(np.mean([d["s"] for d in detail])),
                    "start": stats["start"], "end": stats["end"]}
    return cells


def monthly(fs, rm, membership, stocks, etf, volume):
    index = etf.index
    close_ff = stocks.ffill()
    returns = stocks.pct_change(fill_method=None)
    factors = rm.factor_returns(etf[list(rm.FACTOR_ETFS)])
    dollar = (stocks * volume)
    dv126 = dollar.rolling(126, min_periods=100).mean()
    amihud = (returns.abs() / dollar.replace(0, np.nan)).rolling(126, min_periods=100).mean()
    decisions = [d for d in index[month_ends(index)] if d >= pd.Timestamp(fs.FIRST_DECISION)]
    k = lambda n, frac: max(1, int(round(frac * n)))
    rows = {n: [] for n in ("parent", "nojan", "illiq", "liquid", "lowdv", "highdv")}
    picks_rows = []
    for date, members in zip(decisions, members_on(membership, decisions)):
        t_pos = index.get_loc(date)
        priced = [t for t in sorted(members) if t in stocks.columns and pd.notna(stocks.at[date, t])]
        res = rm.residual_scores(returns, factors, t_pos, priced, **fs.RESMOM6_1)
        picks = equal(top(res, k(len(res), 0.1)))
        rows["parent"].append((date, picks, list(res.index), priced))
        rows["nojan"].append((date, equal(priced) if date.month == 12 else picks, priced if date.month == 12 else list(res.index), priced))
        a = amihud.loc[date, priced].replace([np.inf, -np.inf], np.nan).dropna()
        rows["illiq"].append((date, equal(top(a, k(len(a), 0.2))), list(a.index), priced))
        rows["liquid"].append((date, equal(top(-a, k(len(a), 0.2))), list(a.index), priced))
        d = dv126.loc[date, priced].dropna()
        rows["lowdv"].append((date, equal(top(-d, k(len(d), 0.2))), list(d.index), priced))
        rows["highdv"].append((date, equal(top(d, k(len(d), 0.2))), list(d.index), priced))
        picks_rows.append((date, picks, list(res.index), priced))
    out = {n: run_rule(r, close_ff, index) for n, r in rows.items()}
    # volatility-scaled tilt
    par_run = simulate(close_ff, targets_from(rows["parent"], close_ff, index), 5.0)["returns"]
    bench_t = pd.DataFrame(np.nan, index, close_ff.columns)
    for date, _, _, priced in rows["parent"]:
        bench_t.loc[date] = 0.0
        bench_t.loc[date, priced] = 1.0 / len(priced)
    active = par_run - simulate(close_ff, bench_t, 5.0)["returns"]
    sd126 = active.rolling(126, min_periods=126).std()
    seen, srows = [], []
    for date, picks, ranked, priced in picks_rows:
        cur = sd126.get(date, np.nan)
        s = 1.0
        if pd.notna(cur) and index.get_loc(date) >= index.get_loc(rows["parent"][0][0]) + 252:
            seen.append(cur)
            s = float(min(1.0, np.median(seen) / cur))
        elif pd.notna(cur):
            seen.append(cur)
        srows.append((date, picks, ranked, priced, s))
    out["tilt"] = run_rule_s(srows, close_ff, index)
    for name, c in out.items():
        print(f"{name:8s}", "  ".join(f"{w} {x['net_active']:+6.1%} IR {x['information_ratio']:+5.2f} pl {x['placebo']:.2f} 10bp {x['stress_net_active']:+6.1%} n {x['rebalances']}"
                                      for w, x in c.items() if w in JUDGED) + (f"  mean s {out[name]['IS']['mean_s']:.2f}/{out[name]['OOS']['mean_s']:.2f}" if name == "tilt" else ""), flush=True)
    verdicts = {
        "resmom_volscaled_tilt": bar_fails(out["tilt"]) + [f"{w} IR {out['tilt'][w]['information_ratio']:.2f} not above parent {out['parent'][w]['information_ratio']:.2f}"
                                                         for w in JUDGED if out["tilt"][w]["information_ratio"] <= out["parent"][w]["information_ratio"]],
        "illiq_high_quintile": bar_fails(out["illiq"]),
        "lowdv_quintile": bar_fails(out["lowdv"]),
        "resmom_nojan": bar_fails(out["nojan"]) + [f"{w} net active {out['nojan'][w]['net_active']:.2%} not above parent {out['parent'][w]['net_active']:.2%}"
                                                for w in JUDGED if out["nojan"][w]["net_active"] <= out["parent"][w]["net_active"]],
    }
    return out, verdicts


def acf_fails(cells, parent):
    fails = []
    for w in JUDGED:
        c = cells[w]
        if c["decisions"] < MIN_DECISIONS[w]:
            fails.append(f"{w} only {c['decisions']} decisions")
        if c["net_active"] < BAR["net_active"]:
            fails.append(f"{w} net active {c['net_active']:.2%} < 2.0%")
        if c["information_ratio"] < BAR["information_ratio"]:
            fails.append(f"{w} IR {c['information_ratio']:.2f} < 0.3")
        if c["placebo"] < BAR["placebo"]:
            fails.append(f"{w} placebo {c['placebo']:.3f} < 0.95")
        if c["stress_net_active"] <= 0:
            fails.append(f"{w} 10 bps {c['stress_net_active']:.2%} not above 0")
        if c["net_active"] <= parent[w]["net_active"]:
            fails.append(f"{w} net active {c['net_active']:.2%} not above parent {parent[w]['net_active']:.2%}")
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
    fs, rm, sh = load_module("factor_scan_v1"), load_module("residual_momentum_v1"), load_module("short_horizon_v5")
    membership, stocks, etf = load_inputs(fs, rm)
    index, cols = etf.index, list(stocks.columns)
    volume = load_member_panel(cols, "volume").reindex(index)[cols]
    print("== monthly ==", flush=True)
    mout, verdicts = monthly(fs, rm, membership, stocks, etf, volume)

    print("== daily ==", flush=True)
    fs.FIRST_DECISION = sh.FIRST_DECISION
    mask = member_mask(membership, index, cols) & stocks.notna()
    ret = stocks.pct_change(fill_method=None)
    acf = ret.rolling(126, min_periods=100).corr(ret.shift(1))
    med = acf.where(mask).median(axis=1)
    rev = -(stocks / stocks.shift(5) - 1)
    neg = rev.where(acf.lt(med, axis=0))
    pos = rev.where(acf.ge(med, axis=0))
    start = index.searchsorted(pd.Timestamp(sh.FIRST_DECISION))
    dirty = dirty_index(index)
    sample = set(sample_tickers())
    unseen = [c for c in cols if c not in sample]
    units = {"parent": (sh.PARENT_RULE, None, rev), "acfneg": (sh.PARENT_RULE, None, neg), "acfpos": (sh.PARENT_RULE, None, pos)}
    phase = {}
    for ph in range(3):
        decisions = list(index[start + ph::3])
        phase[ph] = {"screen_all": daily_eval(f"ph{ph} all", stocks, units, None, sh, fs, membership, decisions, dirty)}
        if ph == 0:
            phase[ph]["screen_unseen"] = daily_eval("ph0 unseen", stocks[unseen], {k_: (u[0], u[1], u[2][unseen]) for k_, u in units.items()},
                                                    None, sh, fs, membership, decisions, dirty)
    verdicts["rev5_acfneg_h3_band40_s"] = sum((acf_fails(phase[0][ev]["acfneg"], phase[0][ev]["parent"]) for ev in phase[0]), [])
    other = {ph: acf_fails(phase[ph]["screen_all"]["acfneg"], phase[ph]["screen_all"]["parent"]) for ph in (1, 2)}
    for rid, fails in verdicts.items():
        print(rid, "PASS the screen" if not fails else "FAIL", "; ".join(fails))
    print("other phases (report only):", {ph: ("clears" if not f else "fails") for ph, f in other.items()})
    if args.dry:
        return
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = pd.Timestamp.now("UTC").strftime("%Y%m%dT%H%M%SZ")
    path = OUT_DIR / f"tests_{stamp}.json"
    ref = str(path.relative_to(ROOT))
    key = {"resmom_volscaled_tilt": "tilt", "illiq_high_quintile": "illiq", "lowdv_quintile": "lowdv", "resmom_nojan": "nojan"}
    for rid, fails in verdicts.items():
        if rid in key:
            c = mout[key[rid]]
            body = "; ".join(f"{w} {c[w]['net_active']:.2%}/yr (IR {c[w]['information_ratio']:.2f}, placebo {c[w]['placebo']:.3f}, 10 bps {c[w]['stress_net_active']:.2%})" for w in JUDGED)
        else:
            body = "; ".join(f"{ev} " + ", ".join(f"{w} {phase[0][ev]['acfneg'][w]['net_active']:.2%}/yr (IR {phase[0][ev]['acfneg'][w]['information_ratio']:.2f}, placebo {phase[0][ev]['acfneg'][w]['placebo']:.3f})" for w in JUDGED) for ev in phase[0])
        add_evidence(conn, ids[rid], "backtest", f"round23_tests {rid}: {'passes the screen' if not fails else 'fails'}. {body}." +
                     (f" Fails: {'; '.join(fails)}." if fails else ""), "supports" if not fails else "contradicts", ref=ref)
        set_status(conn, ids[rid], "rejected" if fails else ("testing" if rid == "rev5_acfneg_h3_band40_s" else "supported"))
    path.write_text(json.dumps({"git_commit": _git_commit(), "run_at": stamp, "monthly": mout, "daily": phase, "verdicts": verdicts}, indent=1, default=str) + "\n")
    conn.close()
    print(f"wrote {ref}")


if __name__ == "__main__":
    sys.exit(main())
