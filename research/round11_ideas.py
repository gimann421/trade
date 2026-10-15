"""Score hypotheses 112-120 of research/r11-cost-and-signal-ideas-2026-10-15.md and the gap-fade screens (B4).

    PYTHONPATH=. python research/round11_ideas.py --register
    PYTHONPATH=. python research/round11_ideas.py --universe all        # every member with snapshots (718); evidence
    PYTHONPATH=. python research/round11_ideas.py --universe holdout    # the 418 names outside the round-9 sample; evidence
    PYTHONPATH=. python research/round11_ideas.py --finalize            # combine the two latest files, set statuses
    PYTHONPATH=. python research/round11_ideas.py --gap                 # B4 gross screens, report only
"""

import argparse
import json
import sys

import numpy as np
import pandas as pd

from core.backtest import _git_commit
from core.config import ROOT
from core.data import load_bars
from core.edgar import load_events, reaction_sessions
from core.industry import load_sic
from core.ledger import add_evidence, add_hypothesis, connect, set_status, set_strategy
from core.portfolio import month_ends, simulate
from core.universe import members_on
from research.round5_verdicts import holding_windows, in_window, window_stats
from research.round6_scan import load_module, lookup
from research.round8_short_horizon import (BAR, COSTS, WINDOWS, break_even_bps, cleaned, dirty_index, placebo,
                                           weeks_to_confidence)
from research.round10_neighbours import MIN_AGREE, MIN_DECISIONS, load_inputs

MEMO = "research/r11-cost-and-signal-ideas-2026-10-15.md"
HYPOTHESES_BEFORE = 111
OUT_DIR = ROOT / "backtests" / "short_horizon_v4"
GAP_MIN_GROSS = 0.25


def title_of(rule: dict) -> str:
    return f"Short-horizon v4: {rule['id']}"


def describe(rule: dict) -> str:
    return (f"Round 11 variant {rule['signal']}{' without topping up' if rule['no_top_up'] else ''}: every {rule['hold']} "
            f"sessions, reading the 15:45 price and filling at the close, holding the top 10% with a keep-while-top-"
            f"{rule['band']:.0%} band of point-in-time S&P 500 members, equal weight start, beats the equal-weight members "
            f">= 2.0%/yr net with IR >= 0.3, placebo >= 0.95, positive at 10 bps, in both IS 2017-2022 and OOS 2023+, "
            f"on all 718 names and on the 418 unseen names.")


def register(conn, rules) -> dict:
    ids = lookup(conn)
    for rule in rules:
        if title_of(rule) not in ids:
            ids[title_of(rule)] = add_hypothesis(conn, title_of(rule), describe(rule),
                                                 rationale="Round 11: cut the cost or sharpen the signal of the band reversal rule.",
                                                 research_memo=MEMO, strategy="short_horizon_v4.py")
    return {r["id"]: ids[title_of(r)] for r in rules}


def judge(label, decisions, minimum, stats, pct, stress_active, noisy_active):
    if decisions < minimum[label]:
        return "inconclusive", [f"only {decisions} decisions (need {minimum[label]})"]
    fails = []
    if stats["net_active"] < BAR["net_active"]:
        fails.append(f"net active {stats['net_active']:.2%}/yr < 2.0%")
    if stats["information_ratio"] < BAR["information_ratio"]:
        fails.append(f"information ratio {stats['information_ratio']:.2f} < 0.3")
    if pct < BAR["placebo"]:
        fails.append(f"placebo {pct:.3f} < 0.95")
    if stress_active <= 0:
        fails.append(f"10 bps net active {stress_active:.2%} not above 0")
    if noisy_active is not None and noisy_active <= 0:
        fails.append(f"15:30-signal net active {noisy_active:.2%} not above 0")
    return ("contradicts", fails) if fails else ("supports", ["passes the bar and the stress checks"])


def run(universe: str):
    sh = load_module("short_horizon_v4")
    fs = load_module("factor_scan_v1")
    conn = connect()
    ids = register(conn, sh.RULES)
    membership, index, close, open_, snaps, report = load_inputs(None, universe)
    print("data check:", json.dumps(report))
    if min(report[f]["share_within"] for f in ("p1530", "p1545")) < MIN_AGREE:
        print("snapshot data fails the pre-registered agreement check; stopping")
        return
    full = close.copy()
    full[sh.CASH] = load_bars("BIL")["close"].reindex(index)
    close_ff = full.ffill()
    cols = list(full.columns)
    dirty = dirty_index(index)
    fs.FIRST_DECISION = sh.FIRST_DECISION
    members_fn = lambda dates: members_on(membership, dates)
    monthly = index[month_ends(index)]
    probe = {"family": "stock", "fraction": 0.1, "hold": 1, "trend": False}
    _, bench_targets, bench_detail = fs.generate_targets(probe, full, pd.DataFrame(np.nan, index, cols), monthly, membership, None)
    bench = {n: cleaned(simulate(close_ff, bench_targets, b), dirty) for n, b in COSTS.items()}
    first_hold = index[index.get_loc(bench_detail[0]["date"]) + 1]

    sic = load_sic()
    events = load_events()
    events["reaction"] = reaction_sessions(events["acceptance_utc"], index)
    exclude = sh.exclusion_mask(events, index, cols)
    print(f"sic codes for {sum(c in sic.index for c in cols)}/{len(cols)} names; earnings dates for "
          f"{events['symbol'].isin(cols).sum()} releases across {events.loc[events['symbol'].isin(cols), 'symbol'].nunique()} names", flush=True)

    def mats(signal, price):
        s45 = snaps["p1545"].reindex(columns=cols) if price == "p1545" else snaps["p1530"].reindex(columns=cols)
        full_open = open_.reindex(columns=cols)
        sc = sh.score_matrix(signal, full_open, full, snaps["p1545"].reindex(columns=cols) if signal.startswith("l15") else s45,
                             snaps["p1530"].reindex(columns=cols))
        sc[sh.CASH] = np.nan
        sc2 = None
        if signal == "blend":
            sc2 = sh.id5_matrix(full_open, full, s45)
            sc2[sh.CASH] = np.nan
        return sc, sc2

    rules = sh.PARENT_RULES + sh.RULES
    results, stamp = {}, pd.Timestamp.now("UTC").strftime("%Y%m%dT%H%M%SZ")
    path = OUT_DIR / f"short_horizon_v4_{universe}_{stamp}.json"
    for rule in rules:
        decisions = sh.decision_dates(index, rule["hold"])
        runs, details = {}, {}
        variants = [("primary", "p1545", 5.0), ("stress", "p1545", 10.0)]
        if not rule["signal"].startswith("l15"):
            variants.append(("noisy", "p1530", 5.0))
        for variant, price, bps in variants:
            sc, sc2 = mats(rule["signal"], price)
            targets, detail = sh.generate_targets(rule, full, sc, decisions, members_fn, scores2=sc2,
                                                  groups=sic if rule["signal"] == "rev5n" else None,
                                                  exclude=exclude if rule["signal"] == "rev5x" else None)
            runs[variant] = cleaned(simulate(close_ff, targets, bps), dirty)
            details[variant] = detail
        windows = holding_windows(details["primary"], index)
        cells = {}
        for label, (start, end) in WINDOWS.items():
            _, _, stats = window_stats(runs["primary"], bench["primary"], first_hold, start, end)
            net = lambda name, b: window_stats(runs[name], bench[b], first_hold, start, end)[2]["net_active"]
            stress_active = net("stress", "stress")
            noisy_active = net("noisy", "primary") if "noisy" in runs else None
            _, pct = placebo(details["primary"], close_ff, index, start, end, dirty)
            n = sum(in_window(first, start, end) for _, first, _ in windows)
            extra = stats["annual_turnover"] - stats["benchmark_annual_turnover"]
            gross = stats["net_active"] + extra * COSTS["primary"] / 1e4
            verdict, why = judge(label, n, MIN_DECISIONS[rule["hold"]], stats, pct, stress_active, noisy_active)
            cells[label] = {"verdict": verdict, "why": why, "decisions": n, "net_active": stats["net_active"],
                            "information_ratio": stats["information_ratio"], "placebo": pct, "gross_active": gross,
                            "annual_turnover": stats["annual_turnover"], "break_even_bps": break_even_bps(gross, extra),
                            "stress_net_active": stress_active, "noisy_net_active": noisy_active,
                            "beta": stats["beta_to_benchmark"], "start": stats["start"], "end": stats["end"]}
        whole = window_stats(runs["primary"], bench["primary"], first_hold, "2016-01-01", None)[2]
        results[rule["id"]] = {"rule": rule, "cells": cells, "information_ratio_all": whole["information_ratio"],
                               "net_active_all": whole["net_active"],
                               "weeks_to_confidence": weeks_to_confidence(whole["information_ratio"])}
        print(f"{rule['id']:20s} " + "  ".join(
            f"{w} act {c['net_active']:+6.1%} IR {c['information_ratio']:+5.2f} pl {c['placebo']:.2f} gross {c['gross_active']:+6.1%} "
            f"turn {c['annual_turnover']:4.0f} 10bp {c['stress_net_active']:+6.1%} "
            f"1530 {('n/a' if c['noisy_net_active'] is None else format(c['noisy_net_active'], '+6.1%'))}"
            for w, c in cells.items()) + "  -> " + "/".join(c["verdict"] for c in cells.values()), flush=True)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ledger_ids = lookup(conn)
    for rid, res in results.items():
        if res["rule"]["role"] == "parent":
            continue
        hid = ledger_ids[title_of(res["rule"])]
        for w, c in res["cells"].items():
            be = f"{c['break_even_bps']:.1f}" if c["break_even_bps"] is not None else "n/a"
            noisy = "n/a" if c["noisy_net_active"] is None else f"{c['noisy_net_active']:.2%}"
            summary = (f"short_horizon_v4 {rid} [{universe} universe, {report['tickers']} tickers] {w} {c['start']}..{c['end']}, 5 bps, 15:45 snapshot fill at the close: "
                       f"{c['decisions']} decisions, net active {c['net_active']:.2%}/yr (gross {c['gross_active']:.2%}), IR {c['information_ratio']:.2f}, "
                       f"placebo {c['placebo']:.3f}, turnover {c['annual_turnover']:.0f}x/yr, break-even {be} bps; 10 bps {c['stress_net_active']:.2%}, "
                       f"15:30 signal {noisy}. {c['verdict']}: {'; '.join(c['why'])}")
            add_evidence(conn, hid, "backtest", summary, c["verdict"], ref=str(path.relative_to(ROOT)))
    conn.close()
    path.write_text(json.dumps({"git_commit": _git_commit(), "run_at": stamp, "universe": universe, "data_check": report,
                                "bar": BAR, "costs": COSTS, "results": results}, indent=1, default=str) + "\n")
    print(f"wrote {path.relative_to(ROOT)}")


def latest(universe):
    files = sorted(OUT_DIR.glob(f"short_horizon_v4_{universe}_*.json"))
    return json.loads(files[-1].read_text()) if files else None


def finalize():
    sh = load_module("short_horizon_v4")
    a, h = latest("all"), latest("holdout")
    conn = connect()
    ledger_ids = lookup(conn)
    passing = []
    for rule in sh.RULES:
        rid = rule["id"]
        flags = {}
        for name, data in (("all", a), ("holdout", h)):
            cells = data["results"][rid]["cells"]
            flags[name] = all(c["verdict"] == "supports" for c in cells.values())
        direction = True
        if rule["signal"].startswith("l15"):
            sib = next(r for r in sh.RULES if r["id"] == rule["parent"])["id"]
            direction = all(a["results"][rid]["cells"][w]["net_active"] > a["results"][sib]["cells"][w]["net_active"]
                            for w in ("IS", "OOS"))
        gross_ok = any(c["gross_active"] >= 0.04 for c in a["results"][rid]["cells"].values())
        supported = flags["all"] and flags["holdout"] and direction and gross_ok
        rejected = any(c["verdict"] == "contradicts" for d in (a, h) for c in d["results"][rid]["cells"].values())
        status = "supported" if supported else "rejected" if rejected else "testing"
        if supported:
            passing.append(rid)
        hid = ledger_ids[title_of(rule)]
        set_strategy(conn, hid, "short_horizon_v4.py")
        set_status(conn, hid, status)
        print(f"{rid:20s} all={flags['all']} holdout={flags['holdout']} direction={direction} -> {status}")
    base = ledger_ids["Short-horizon v2: rev5_h2_band_s"] if "Short-horizon v2: rev5_h2_band_s" in ledger_ids else None
    note = (f"Round 11 (hypotheses 112-120): {len(passing)} of {len(sh.RULES)} rules pass the raised bar "
            f"(all 718 names and the 418 unseen): {', '.join(passing) or 'none'}. Hypotheses tested so far: {HYPOTHESES_BEFORE + len(sh.RULES)}.")
    if base:
        add_evidence(conn, base, "note", note, "inconclusive")
    conn.close()
    print(note)


def gap_screens():
    from research.round10_neighbours import load_inputs as li
    membership, index, close, open_, _, report = li(None, "all")
    dirty = set(dirty_index(index))
    prev = close.shift(1)
    gap = open_ / prev - 1
    day = close / open_ - 1
    rows = {"all": {}, "big": {}}
    for date, cands in zip(index, members_on(membership, list(index))):
        if date in dirty or date < pd.Timestamp("2017-01-03"):
            continue
        names = [t for t in cands if t in close.columns and pd.notna(gap.at[date, t]) and pd.notna(day.at[date, t])]
        if len(names) < 20:
            continue
        g, r = gap.loc[date, names], day.loc[date, names]
        for key, pool in (("all", g), ("big", g[g.abs() >= 0.02])):
            if len(pool) < 10:
                continue
            n = max(1, int(round(0.1 * len(pool))))
            pick = pool.sort_values().index[:n]            # most negative gap first (fade down-gaps)
            rows[key][date] = (r[pick].mean() - r.mean(), r[pick].mean())
    out = {}
    for key, series in rows.items():
        frame = pd.DataFrame(series, index=["active", "pick"]).T
        for label, (start, end) in WINDOWS.items():
            part = frame.loc[max(pd.Timestamp(start), pd.Timestamp("2017-01-03")):end if end else None]
            out[f"{key}_{label}"] = {"days": len(part), "gross_active_per_year": float(part["active"].mean() * 252),
                                      "pick_mean_per_year": float(part["pick"].mean() * 252)}
    advance = {k: all(out[f"{k}_{w}"]["gross_active_per_year"] >= GAP_MIN_GROSS for w in ("IS", "OOS")) for k in ("all", "big")}
    print(json.dumps({"screens": out, "advance": advance}, indent=1))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "gap_fade_screens.json").write_text(json.dumps({"screens": out, "advance": advance}, indent=1) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--register", action="store_true")
    parser.add_argument("--universe", choices=["all", "holdout"])
    parser.add_argument("--finalize", action="store_true")
    parser.add_argument("--gap", action="store_true")
    args = parser.parse_args()
    if args.register:
        conn = connect()
        ids = register(conn, load_module("short_horizon_v4").RULES)
        print(f"{len(ids)} rules registered, ids {min(ids.values())}-{max(ids.values())}")
    elif args.finalize:
        finalize()
    elif args.gap:
        gap_screens()
    elif args.universe:
        run(args.universe)


if __name__ == "__main__":
    sys.exit(main())
