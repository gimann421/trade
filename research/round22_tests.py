"""Round 22: volatility term structure, vol-of-vol and short-term stress as scalers of the band reversal rule, and a VIX/VIX3M timing rule
(research/r22-vol-term-structure-2026-10-20.md).

    PYTHONPATH=. python research/round22_data.py
    PYTHONPATH=. python research/round22_tests.py --register
    PYTHONPATH=. python research/round22_tests.py [--dry]
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
from core.universe import load_member_panel, members_on
from research.round22_data import load as load_cboe
from research.round5_verdicts import holding_windows, in_window, window_stats
from research.round6_scan import BAR, load_inputs, load_module, lookup
from research.round8_short_horizon import cleaned, dirty_index, placebo as daily_placebo
from research.round8_short_horizon import WINDOWS

MEMO = "research/r22-vol-term-structure-2026-10-20.md"
OUT_DIR = ROOT / "backtests" / "round22_tests"
MIN_DECISIONS = {"IS": 160, "OOS": 100}
JUDGED = ("IS", "OOS")
HYP = {
    "rev5_vts_scale": "The band reversal rule with its active share scaled by the VIX/VIX3M ratio (vixscale form) passes the bar in both windows on both screens and beats both the plain parent and the VIX-level scaler",
    "rev5_vvix_scale": "The band reversal rule with its active share scaled by VVIX (vixscale form) passes the bar in both windows on both screens and beats both the plain parent and the VIX-level scaler",
    "rev5_vx9_scale": "The band reversal rule with its active share scaled by VIX9D/VIX (vixscale form) passes the bar in both windows on both screens and beats both the plain parent and the VIX-level scaler",
    "vts_timing_vti": "Holding VTI only while the previous session's VIX/VIX3M is below 1 (else BIL) passes the bar in both windows against buy-and-hold VTI",
}


def register(conn):
    ids = lookup(conn)
    for rid, statement in HYP.items():
        title = f"Round 22: {rid}"
        if title not in ids:
            ids[title] = add_hypothesis(conn, title, statement + f" (see {MEMO}); pre-registered criteria in the memo.",
                                        rationale="Round 22: Cboe volatility indices as scalers and timing, keep testing until one passes.",
                                        research_memo=MEMO, strategy="round22_tests.py")
    return {rid: ids[f"Round 22: {rid}"] for rid in HYP}


def states():
    vix, v3m, v9d, vvix = (load_cboe(n) for n in ("VIX", "VIX3M", "VIX9D", "VVIX"))
    both = lambda a, b: (a / b).dropna()
    return {"vixlevel": vix, "vts": both(vix, v3m), "vvix": vvix, "vx9": both(v9d, vix)}


def daily_eval(label, close, units, shares, sh, fs, membership, decisions, dirty):
    index = close.index
    full = close.copy()
    full[sh.CASH] = load_bars("BIL")["close"].reindex(index)
    close_ff = full.ffill()
    members_fn = lambda dates: members_on(membership, dates)
    probe = {"family": "stock", "fraction": 0.1, "hold": 1, "trend": False}
    monthly_dec = index[month_ends(index)]
    _, bench_targets, bdetail = fs.generate_targets(probe, full, pd.DataFrame(np.nan, index, full.columns), monthly_dec, membership, None)
    first_hold = index[index.get_loc(bdetail[0]["date"]) + 1]
    bench = {k: cleaned(simulate(close_ff, bench_targets, bps), dirty) for k, bps in (("5", 5.0), ("10", 10.0))}
    score = -(close / close.shift(5) - 1)
    score[sh.CASH] = np.nan
    score = score.reindex(columns=full.columns)
    results = {}
    for unit, spec in units.items():
        rule, share = spec[:2]
        unit_score = score if len(spec) < 3 else spec[2].reindex(index=index, columns=full.columns)
        targets, detail = sh.generate_targets(rule, full, unit_score, decisions, members_fn, share=share)
        run5, run10 = (cleaned(simulate(close_ff, targets, bps), dirty) for bps in (5.0, 10.0))
        windows = holding_windows(detail, index)
        cells = {}
        for w, (start, end) in WINDOWS.items():
            _, _, stats = window_stats(run5, bench["5"], first_hold, start, end)
            stress = window_stats(run10, bench["10"], first_hold, start, end)[2]["net_active"]
            _, pct = daily_placebo(detail, close_ff, index, start, end, dirty)
            n = sum(in_window(first, start, end) for _, first, _ in windows)
            cells[w] = {"decisions": n, "net_active": stats["net_active"], "information_ratio": stats["information_ratio"], "placebo": pct,
                        "stress_net_active": stress, "mean_share": float(np.mean([d["share"] for d in detail]))}
        results[unit] = cells
        print(label, f"{unit:14s}", "  ".join(f"{w} {c['net_active']:+6.1%} IR {c['information_ratio']:+5.2f} pl {c['placebo']:.2f} "
                                              f"10bp {c['stress_net_active']:+6.1%} share {c['mean_share']:.2f} n {c['decisions']}"
                                              for w, c in cells.items()), flush=True)
    return results


def daily_fails(cells, parent, vixlevel):
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
        for name, ref in (("parent", parent), ("VIX-level scaler", vixlevel)):
            if c["net_active"] <= ref[w]["net_active"]:
                fails.append(f"{w} net active {c['net_active']:.2%} not above {name} {ref[w]['net_active']:.2%}")
    return fails


def timing(etf, state):
    """VTI while the previous session's state ratio is below 1, else BIL; circular-shift placebo."""
    index = etf.index
    close = etf[["VTI", "BIL"]].ffill()
    s = state.reindex(state.index.union(index)).ffill().reindex(index).shift(1)
    inmkt = (s < 1.0) | s.isna()
    targets = pd.DataFrame({"VTI": inmkt.astype(float), "BIL": (~inmkt).astype(float)}, index)
    bench_t = pd.DataFrame({"VTI": 1.0, "BIL": 0.0}, index)
    first_hold = index[1]
    runs = {bps: simulate(close, targets, bps) for bps in (5.0, 10.0)}
    benches = {bps: simulate(close, bench_t, bps) for bps in (5.0, 10.0)}
    g_vti, g_bil = close["VTI"].shift(-1) / close["VTI"] - 1, close["BIL"].shift(-1) / close["BIL"] - 1
    out = {}
    for w, (start, end) in {k: v for k, v in WINDOWS.items()}.items():
        _, _, stats = window_stats(runs[5.0], benches[5.0], first_hold, start, end)
        stress = window_stats(runs[10.0], benches[10.0], first_hold, start, end)[2]["net_active"]
        sel = (index >= pd.Timestamp(start)) & ((index <= pd.Timestamp(end)) if end else True) & g_vti.notna().to_numpy()
        gap = (g_bil - g_vti).to_numpy()[sel]
        flags = (~inmkt).to_numpy()[sel].astype(float)
        actual = float((flags * gap).mean())
        rng = np.random.default_rng(0)
        draws = np.array([(np.roll(flags, int(rng.integers(1, len(flags)))) * gap).mean() for _ in range(1000)])
        out[w] = {"net_active": stats["net_active"], "information_ratio": stats["information_ratio"], "placebo": float((draws < actual).mean()),
                  "stress_net_active": stress, "days": int(sel.sum()), "off_share": float(flags.mean()), "turnover": stats["annual_turnover"]}
        c = out[w]
        print("timing", w, f"{c['net_active']:+6.1%} IR {c['information_ratio']:+5.2f} pl {c['placebo']:.2f} 10bp {c['stress_net_active']:+6.1%} "
                           f"off {c['off_share']:.1%} turn {c['turnover']:.1f} days {c['days']}", flush=True)
    return out


def timing_fails(cells):
    fails = []
    for w in JUDGED:
        c = cells[w]
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
    fs, rm, sh = load_module("factor_scan_v1"), load_module("residual_momentum_v1"), load_module("short_horizon_v5")
    fs.FIRST_DECISION = sh.FIRST_DECISION
    membership, stocks, etf = load_inputs(fs, rm)
    index = etf.index
    st = states()
    shares = {k: sh.vix_share(v, index, "scale") for k, v in st.items()}
    units = {"parent": (sh.PARENT_RULE, None)}
    units["vixlevel"] = ({**sh.PARENT_RULE, "id": "vixscale_ref", "vix": "scale"}, shares["vixlevel"])
    for rid, key in (("rev5_vts_scale", "vts"), ("rev5_vvix_scale", "vvix"), ("rev5_vx9_scale", "vx9")):
        units[rid] = ({**sh.PARENT_RULE, "id": rid, "vix": "scale"}, shares[key])
    decisions = sh.decision_dates(index)
    dirty = dirty_index(index)
    sample = set(sample_tickers())
    unseen = [c for c in stocks.columns if c not in sample]
    dout = {"screen_all": daily_eval("screen_all", stocks, units, shares, sh, fs, membership, decisions, dirty),
            "screen_unseen": daily_eval("screen_unseen", stocks[unseen], units, shares, sh, fs, membership, decisions, dirty)}
    tout = timing(etf, st["vts"])
    verdicts = {rid: sum((daily_fails(dout[ev][rid], dout[ev]["parent"], dout[ev]["vixlevel"]) for ev in dout), [])
                for rid in ("rev5_vts_scale", "rev5_vvix_scale", "rev5_vx9_scale")}
    verdicts["vts_timing_vti"] = timing_fails(tout)
    for rid, fails in verdicts.items():
        print(rid, "PASS the screen" if not fails else "FAIL", "; ".join(fails))
    if args.dry:
        return
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = pd.Timestamp.now("UTC").strftime("%Y%m%dT%H%M%SZ")
    path = OUT_DIR / f"tests_{stamp}.json"
    ref = str(path.relative_to(ROOT))
    for rid, fails in verdicts.items():
        if rid == "vts_timing_vti":
            body = "; ".join(f"{w} {tout[w]['net_active']:.2%}/yr (IR {tout[w]['information_ratio']:.2f}, placebo {tout[w]['placebo']:.3f}, 10 bps {tout[w]['stress_net_active']:.2%})" for w in JUDGED)
        else:
            body = "; ".join(f"{ev} " + ", ".join(f"{w} {dout[ev][rid][w]['net_active']:.2%}/yr (IR {dout[ev][rid][w]['information_ratio']:.2f}, placebo {dout[ev][rid][w]['placebo']:.3f})" for w in JUDGED) for ev in dout)
        add_evidence(conn, ids[rid], "backtest", f"round22_tests {rid}: {'passes the screen' if not fails else 'fails'}. {body}." +
                     (f" Fails: {'; '.join(fails)}." if fails else ""), "supports" if not fails else "contradicts", ref=ref)
        set_status(conn, ids[rid], "rejected" if fails else ("supported" if rid == "vts_timing_vti" else "testing"))
    path.write_text(json.dumps({"git_commit": _git_commit(), "run_at": stamp, "daily": dout, "timing": tout, "verdicts": verdicts}, indent=1, default=str) + "\n")
    conn.close()
    print(f"wrote {ref}")


if __name__ == "__main__":
    sys.exit(main())
