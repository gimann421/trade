"""Round 19: overnight momentum, sector-adjusted residual momentum, volume attention, and three reversal rankings
(research/r19-overnight-sector-volume-reversal-2026-10-20.md).

    PYTHONPATH=. python research/round19_tests.py --register
    PYTHONPATH=. python research/round19_tests.py [--dry]
"""

import argparse
import json
import sys

import numpy as np
import pandas as pd

from core.backtest import _git_commit
from core.config import ROOT
from core.data import load_bars
from core.intraday import sample_tickers
from core.ledger import add_evidence, add_hypothesis, connect, set_status
from core.portfolio import month_ends, simulate
from core.universe import (FIRST_MONTH_END, LAST_MONTH_END, load_member_panel, load_membership, members_on,
                           month_end_members)
from research.round5_verdicts import holding_windows, in_window, window_stats
from research.round6_scan import BAR, load_inputs, load_module, lookup
from research.round8_short_horizon import WINDOWS as DAILY_WINDOWS
from research.round8_short_horizon import cleaned, dirty_index, placebo as daily_placebo
from research.round18_tests import JUDGED, bar_fails, equal, run_rule, top

MEMO = "research/r19-overnight-sector-volume-reversal-2026-10-20.md"
OUT_DIR = ROOT / "backtests" / "round19_tests"
HYPOTHESES_BEFORE = 151
FIRST_DECISION, HOLD, RULE_ID = "2017-01-03", 3, "rev5_h3_band40_s"
MIN_DECISIONS = {"IS": 160, "OOS": 100}
HYP = {
    "onmom6_1_decile": "Holding the top 10% of S&P 500 members by 6-1 cumulative overnight return passes the bar in both windows against the equal-weight members",
    "resmom_sector_decile": "Residual momentum 6-1 with nine sector spreads added to the regression factors passes the bar in both windows and beats the shadow parent's information ratio in both",
    "resmom_volrise_decile": "Residual momentum 6-1 among names whose 3-month volume is at or above the median ratio to 12-month volume passes the bar in both windows and beats the same-set parent's net active in both",
    "rev5z_h3_band40_s": "The 3-session band reversal rule ranked on the 5-session return scaled by 60-session volatility passes the bar in both windows and beats the parent's net active",
    "rev5ibs_h3_band40_s": "The 3-session band reversal rule ranked on 5-session return plus a weak day close location passes the bar in both windows and beats the parent's net active",
    "rev5jump_h3_band40_s": "The 3-session band reversal rule ranked on reversing the biggest single-day move of the last 5 sessions passes the bar in both windows and beats the parent's net active",
}


def register(conn):
    ids = lookup(conn)
    for rid, statement in HYP.items():
        title = f"Round 19: {rid}"
        if title not in ids:
            ids[title] = add_hypothesis(conn, title, statement + f" (see {MEMO}); pre-registered criteria in the memo.",
                                        rationale="Round 19: thread-chosen ideas, keep testing until one passes.",
                                        research_memo=MEMO, strategy="round19_tests.py")
    return {rid: ids[f"Round 19: {rid}"] for rid in HYP}


# --- monthly tests -------------------------------------------------------------------------------

def window_sum(frame, t_pos, start_lag, end_lag, min_valid):
    """Sum of a per-session frame over positions t-start_lag..t-end_lag; NaN for names with too few valid sessions."""
    w = frame.iloc[t_pos - start_lag:t_pos - end_lag + 1]
    return w.sum(min_count=1).where(w.notna().sum() >= min_valid)


def monthly(fs, rm, membership, stocks, etf, volume, openp):
    index = etf.index
    close_ff = stocks.ffill()
    returns = stocks.pct_change(fill_method=None)
    factors = rm.factor_returns(etf[list(rm.FACTOR_ETFS)])
    spreads = pd.DataFrame({s: etf[s].pct_change(fill_method=None) - etf["VTI"].pct_change(fill_method=None) for s in fs.SECTORS})
    factors_sector = pd.concat([factors, spreads], axis=1)
    overnight = np.log1p((openp / stocks.shift(1) - 1).where(lambda x: x.abs() <= 0.5))
    intraday = np.log1p((stocks / openp - 1).where(lambda x: x.abs() <= 0.5))
    vol3, vol12 = volume.rolling(63, min_periods=60).mean(), volume.rolling(252, min_periods=200).mean()
    decisions = [d for d in index[month_ends(index)] if d >= pd.Timestamp(fs.FIRST_DECISION)]
    rows = {k: [] for k in ("parent", "onmom", "onmom_low", "intra", "sector", "parent_vol", "volrise", "volfall")}
    for date, members in zip(decisions, members_on(membership, decisions)):
        t_pos = index.get_loc(date)
        priced = [t for t in sorted(members) if t in stocks.columns and pd.notna(stocks.at[date, t])]
        res = rm.residual_scores(returns, factors, t_pos, priced, **fs.RESMOM6_1)
        k = lambda n, frac: max(1, int(round(frac * n)))
        rows["parent"].append((date, equal(top(res, k(len(res), 0.1))), list(res.index), priced))
        # 152: overnight momentum
        on = window_sum(overnight[priced], t_pos, 126, 21, 105).dropna()
        itd = window_sum(intraday[priced], t_pos, 126, 21, 105).dropna()
        rows["onmom"].append((date, equal(top(on, k(len(on), 0.1))), list(on.index), priced))
        rows["onmom_low"].append((date, equal(top(-on, k(len(on), 0.1))), list(on.index), priced))
        rows["intra"].append((date, equal(top(itd, k(len(itd), 0.1))), list(itd.index), priced))
        # 153: sector-adjusted residual momentum
        sec = rm.residual_scores(returns, factors_sector, t_pos, priced, **fs.RESMOM6_1)
        rows["sector"].append((date, equal(top(sec, k(len(sec), 0.1))), list(sec.index), priced))
        # 154: residual momentum among names with rising volume
        ratio = (vol3.loc[date, priced] / vol12.loc[date, priced]).replace([np.inf, -np.inf], np.nan).dropna()
        both = sorted(set(ratio.index) & set(res.index))
        r_both = res[both]
        rise = ratio[both][ratio[both] >= ratio[both].median()].index
        fall = ratio[both][ratio[both] < ratio[both].median()].index
        ok = len(both) >= 20
        rows["parent_vol"].append((date, equal(top(r_both, k(len(both), 0.1))) if ok else {}, both, both))
        rows["volrise"].append((date, equal(top(r_both[rise], k(len(rise), 0.2))) if ok else {}, both, both))
        rows["volfall"].append((date, equal(top(r_both[fall], k(len(fall), 0.2))) if ok else {}, both, both))
    out = {}
    for name, r in rows.items():
        out[name] = run_rule(r, close_ff, index)
        print(f"{name:10s}", "  ".join(f"{w} {c['net_active']:+6.1%} IR {c['information_ratio']:+5.2f} pl {c['placebo']:.2f} "
                                       f"10bp {c['stress_net_active']:+6.1%} n {c['rebalances']}" for w, c in out[name].items()), flush=True)
    verdicts = {
        "onmom6_1_decile": bar_fails(out["onmom"]),
        "resmom_sector_decile": bar_fails(out["sector"]) + [
            f"{w} IR {out['sector'][w]['information_ratio']:.2f} not above parent {out['parent'][w]['information_ratio']:.2f}"
            for w in JUDGED if out["sector"][w]["information_ratio"] <= out["parent"][w]["information_ratio"]],
        "resmom_volrise_decile": bar_fails(out["volrise"]) + [
            f"{w} net active {out['volrise'][w]['net_active']:.2%} not above parent {out['parent_vol'][w]['net_active']:.2%}"
            for w in JUDGED if out["volrise"][w]["net_active"] <= out["parent_vol"][w]["net_active"]],
    }
    keys = {"onmom6_1_decile": "onmom", "resmom_sector_decile": "sector", "resmom_volrise_decile": "volrise"}
    return out, verdicts, keys


# --- daily tests ---------------------------------------------------------------------------------

def daily_scores(close, high, low):
    ret = close.pct_change(fill_method=None)
    r5 = close / close.shift(5) - 1
    parent = -r5
    vol60 = ret.rolling(60, min_periods=50).std()
    z = -r5 / (vol60 * np.sqrt(5))
    clv = ((close - low) / (high - low)).where(high > low)
    ibs = (parent.rank(axis=1, pct=True) + (-clv).rank(axis=1, pct=True)) / 2
    ibs = ibs.where(parent.notna() & clv.notna())
    stack = np.stack([ret.shift(i).to_numpy() for i in range(5)])          # (5, T, N)
    arg = np.nanargmax(np.where(np.isnan(stack), -1.0, np.abs(stack)), axis=0)
    jump = pd.DataFrame(-np.take_along_axis(stack, arg[None], axis=0)[0], close.index, close.columns)
    jump = jump.where(pd.DataFrame(~np.isnan(stack).any(axis=0), close.index, close.columns))
    return {"parent": parent, "rev5z_h3_band40_s": z, "rev5ibs_h3_band40_s": ibs, "rev5jump_h3_band40_s": jump}


def daily_eval(label, close, scores, sh, fs, membership, decisions, rule, dirty):
    index = close.index
    full = close.copy()
    full[sh.CASH] = load_bars("BIL")["close"].reindex(index)
    close_ff = full.ffill()
    monthly_dec = index[month_ends(index)]
    probe = {"family": "stock", "fraction": 0.1, "hold": 1, "trend": False}
    _, bench_targets, bdetail = fs.generate_targets(probe, full, pd.DataFrame(np.nan, index, full.columns), monthly_dec, membership, None)
    first_hold = index[index.get_loc(bdetail[0]["date"]) + 1]
    members_fn = lambda dates: members_on(membership, dates)
    bench = {k: cleaned(simulate(close_ff, bench_targets, bps), dirty) for k, bps in (("5", 5.0), ("10", 10.0))}
    results = {}
    for unit, score in scores.items():
        score = score.reindex(index=index, columns=full.columns)
        score[sh.CASH] = np.nan
        targets, detail = sh.generate_targets(rule, full, score, None, decisions, members_fn)
        run5, run10 = (cleaned(simulate(close_ff, targets, bps), dirty) for bps in (5.0, 10.0))
        windows = holding_windows(detail, index)
        cells = {}
        for w, (start, end) in DAILY_WINDOWS.items():
            _, _, stats = window_stats(run5, bench["5"], first_hold, start, end)
            stress = window_stats(run10, bench["10"], first_hold, start, end)[2]["net_active"]
            _, pct = daily_placebo(detail, close_ff, index, start, end, dirty)
            n = sum(in_window(first, start, end) for _, first, _ in windows)
            cells[w] = {"decisions": n, "net_active": stats["net_active"], "information_ratio": stats["information_ratio"],
                        "placebo": pct, "stress_net_active": stress, "turnover": stats["annual_turnover"]}
        results[unit] = cells
        print(label, f"{unit:22s}", "  ".join(f"{w} {c['net_active']:+6.1%} IR {c['information_ratio']:+5.2f} pl {c['placebo']:.2f} "
                                              f"10bp {c['stress_net_active']:+6.1%} turn {c['turnover']:4.0f} n {c['decisions']}"
                                              for w, c in cells.items()), flush=True)
    return results


def daily_fails(cells, parent):
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
    fs, rm, sh = load_module("factor_scan_v1"), load_module("residual_momentum_v1"), load_module("short_horizon_v3")
    sh.FIRST_DECISION = FIRST_DECISION
    fs.FIRST_DECISION = FIRST_DECISION
    membership, stocks, etf = load_inputs(fs, rm)
    index = etf.index
    wanted = list(stocks.columns)
    volume = load_member_panel(wanted, "volume").reindex(index)[stocks.columns]
    openp = load_member_panel(wanted, "open").reindex(index)[stocks.columns]
    high = load_member_panel(wanted, "high").reindex(index)[stocks.columns]
    low = load_member_panel(wanted, "low").reindex(index)[stocks.columns]
    print("== monthly ==", flush=True)
    mout, mverd, mkeys = monthly(fs, rm, membership, stocks, etf, volume, openp)

    print("== daily ==", flush=True)
    rule = next(r for r in sh.RULES if r["id"] == RULE_ID)
    decisions = sh.decision_dates(index, HOLD)
    dirty = dirty_index(index)
    scores = daily_scores(stocks, high, low)
    sample = set(sample_tickers())
    unseen = [c for c in stocks.columns if c not in sample]
    dout = {"screen_all": daily_eval("screen_all", stocks, scores, sh, fs, membership, decisions, rule, dirty)}
    dout["screen_unseen"] = daily_eval("screen_unseen", stocks[unseen], {k: v[unseen] for k, v in scores.items()}, sh, fs,
                                       membership, decisions, rule, dirty)
    dverd = {}
    for rid in ("rev5z_h3_band40_s", "rev5ibs_h3_band40_s", "rev5jump_h3_band40_s"):
        dverd[rid] = {ev: daily_fails(dout[ev][rid], dout[ev]["parent"]) for ev in dout}
    verdicts = {**mverd, **{rid: sum(v.values(), []) for rid, v in dverd.items()}}
    for rid, fails in verdicts.items():
        print(rid, "PASS the screen" if not fails else "FAIL", "; ".join(fails))
    if args.dry:
        return
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = pd.Timestamp.now("UTC").strftime("%Y%m%dT%H%M%SZ")
    path = OUT_DIR / f"tests_{stamp}.json"
    ref = str(path.relative_to(ROOT))
    for rid, fails in verdicts.items():
        if rid in mkeys:
            c = mout[mkeys[rid]]
            body = "; ".join(f"{w} {c[w]['net_active']:.2%}/yr (IR {c[w]['information_ratio']:.2f}, placebo {c[w]['placebo']:.3f}, 10 bps {c[w]['stress_net_active']:.2%})" for w in JUDGED)
        else:
            body = "; ".join(f"{ev} " + ", ".join(f"{w} {dout[ev][rid][w]['net_active']:.2%}/yr (IR {dout[ev][rid][w]['information_ratio']:.2f}, placebo {dout[ev][rid][w]['placebo']:.3f})" for w in JUDGED)
                             for ev in dout)
        summary = f"round19_tests {rid}: {'passes the screen' if not fails else 'fails'}. {body}." + (f" Fails: {'; '.join(fails)}." if fails else "")
        add_evidence(conn, ids[rid], "backtest", summary, "supports" if not fails else "contradicts", ref=ref)
        # a daily rule that clears the screens is only 'testing' until the 15:45 snapshot stage
        set_status(conn, ids[rid], "rejected" if fails else ("testing" if rid in dverd else "supported"))
    path.write_text(json.dumps({"git_commit": _git_commit(), "run_at": stamp, "monthly": mout, "daily": dout,
                                "verdicts": verdicts}, indent=1, default=str) + "\n")
    conn.close()
    print(f"wrote {ref}")


if __name__ == "__main__":
    sys.exit(main())
