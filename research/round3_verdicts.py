"""Score hypotheses 23-30 against the kill rules fixed in their 2026-10-12 round-3 memos.

    PYTHONPATH=. python research/round3_verdicts.py

H23-H25 are monthly-rebalanced portfolios scored on two universes each (core, alternate) against
the same-universe `equal_weight_monthly` benchmark; H26-H30 are single-symbol rules scored per
symbol. Windows: IS 2016-01-01..2022-12-31, OOS 2023-01-01..end of data (2026-10-09), 5 bps.
Every cell is backtested, saved under backtests/, and logged as one ledger evidence row; each
hypothesis then gets a final status:
  supported - every rule in its memo passes (including the placebo)
  rejected  - a cell fails, or a memo's rejecting veto fires, or too few symbols can still pass
  testing   - a veto "blocks SUPPORTED" while the cells would otherwise pass, the placebo fails
              after the cells pass, or inconclusive cells leave the outcome open
The rules are transcribed from the memos and were not changed after seeing results. Reading
choices where a memo is silent are in READING_NOTES.
"""

import json
import math

import numpy as np

from core.backtest import _signals, load_strategy, run_backtest, save_result
from core.config import ROOT
from core.data import load_bars
from core.ledger import add_evidence, connect, set_status, set_strategy
from core.portfolio import (load_portfolio_strategy, portfolio_placebo_percentile, prepare,
                            run_portfolio_backtest)
from core.verdicts import drawdown_rule, placebo_percentile, symbol_status, window_arrays
from research.round2_verdicts import extras

WINDOWS = {"IS": ("2016-01-01", "2022-12-31"), "OOS": ("2023-01-01", None)}
COST_BPS = 5.0
PLACEBO = {"n": 1000, "seed": 0, "min_shift": 252, "threshold": 0.95}
BP = 1e-4
STATUS_VERDICT = {"rejected": "contradicts", "testing": "inconclusive", "supported": "supports"}

READING_NOTES = [
    "Portfolio rule 5 ('Sharpe >= highest benchmark Sharpe - 0.20') is applied to the benchmarks the "
    "engine reports: equal_weight_hold, equal_weight_monthly, inverse_vol_monthly (cash assets "
    "excluded from it, since BIL's tiny volatility would make it nearly all cash) and sixty_forty "
    "when SPY and TLT are both held.",
    "Any failed portfolio cell, including a trade-count miss, makes the idea 'rejected' (the memo "
    "says any miss = REJECTED).",
    "Windows start with holdings carried in; engine 'entries' counts a position already open on the "
    "first day of a window as an entry.",
    "H26 episodes = days the weight drops by at least 0.25 (the 1 -> 0.5 transitions); H27 position "
    "changes = entries + exits; H28 events = entries, and an event's net return is its three "
    "daily net returns plus the exit-day cost.",
    "Overnight memo vetoes 'block SUPPORTED': a cell set that would be supported becomes 'testing'.",
    "Calendar memo veto is a hard reject: in either window, 3 or more symbols with return per "
    "exposure day below buy-and-hold's mean daily return minus 5 bps.",
    "Exit bars stay flat for H28 (no same-bar re-trigger); month-ends come from the exchange calendar.",
]


# --- portfolio ideas (H23-H25) -------------------------------------------------------------

PORTFOLIO = {23: "dual_momentum_v1.py", 24: "canary_momentum_v1.py", 25: "breadth_paa_v1.py"}


def portfolio_cell(result, placebo, label):
    s, benchmarks = result["strategy"], result["benchmarks"]
    b = benchmarks["equal_weight_monthly"]
    best_sharpe = max(m["sharpe"] for m in benchmarks.values())
    need = 12 if label == "IS" else 6
    fails = []
    if s["trades"] < need:
        return "inconclusive", f"only {s['trades']} trades (need {need}): unsupported"
    if s["sharpe"] < b["sharpe"] + 0.10:
        fails.append(f"Sharpe {s['sharpe']:.2f} < equal-weight {b['sharpe']:.2f} + 0.10")
    if s["max_drawdown"] < b["max_drawdown"] + 0.03 - 1e-9:
        fails.append(f"MaxDD {s['max_drawdown']:.1%} not 3pts shallower than {b['max_drawdown']:.1%}")
    if s["cagr"] < b["cagr"] - 0.03:
        fails.append(f"CAGR {s['cagr']:.1%} more than 3pts below {b['cagr']:.1%}")
    if s["sharpe"] < best_sharpe - 0.20:
        fails.append(f"Sharpe {s['sharpe']:.2f} more than 0.20 below best benchmark {best_sharpe:.2f}")
    if placebo < PLACEBO["threshold"]:
        fails.append(f"placebo percentile {placebo:.2f} < 0.95")
    return ("contradicts", "; ".join(fails)) if fails else ("supports", "passes kill rule")


def score_portfolio(hypothesis_id, conn, bars_all):
    filename = PORTFOLIO[hypothesis_id]
    module = load_portfolio_strategy(ROOT / "strategies" / filename)
    set_strategy(conn, hypothesis_id, filename)
    set_status(conn, hypothesis_id, "testing")
    cells = {}
    for universe, config in module.UNIVERSES.items():
        signal_only = tuple(config["signal_only"])
        kwargs = {k: v for k, v in config.items() if k != "signal_only"}
        symbols = list(dict.fromkeys(list(config["risky"]) + list(config.get("canaries", ())) + ["BIL"]))

        def generate(bars, kwargs=kwargs):
            return module.generate_weights(bars, **kwargs)

        bars = {s: bars_all[s] for s in symbols}
        _, close, run = prepare(bars, generate, COST_BPS, 0.0, signal_only)
        for label, (start, end) in WINDOWS.items():
            result = run_portfolio_backtest(bars, generate, COST_BPS, start, end, 0.0, signal_only, ("BIL",))
            path = save_result(result, module, universe, window=f"{result['start']}_{result['end']}")
            placebo = portfolio_placebo_percentile(close, run, start, end, COST_BPS, 0.0, PLACEBO["n"],
                                                   PLACEBO["seed"], PLACEBO["min_shift"])
            verdict, why = portfolio_cell(result, placebo, label)
            s, b = result["strategy"], result["benchmarks"]["equal_weight_monthly"]
            summary = (f"{filename[:-3]} {universe} {label} {result['start']}..{result['end']}, 5 bps: "
                       f"Sharpe {s['sharpe']:.2f} vs equal-weight {b['sharpe']:.2f}, MaxDD "
                       f"{s['max_drawdown']:.1%} vs {b['max_drawdown']:.1%}, CAGR {s['cagr']:.1%} vs "
                       f"{b['cagr']:.1%}, {s['trades']} trades, placebo {placebo:.2f}. {verdict}: {why}")
            add_evidence(conn, hypothesis_id, "backtest", summary, verdict, ref=str(path.relative_to(ROOT)))
            cells[(universe, label)] = {"result": result, "placebo": placebo, "verdict": verdict,
                                        "why": why, "ref": str(path.relative_to(ROOT))}
    status = "supported" if all(c["verdict"] == "supports" for c in cells.values()) else "rejected"
    passing = sum(c["verdict"] == "supports" for c in cells.values())
    note = (f"Round-3 verdict: {status} ({passing}/4 cells pass every rule in the memo; all four must).")
    add_evidence(conn, hypothesis_id, "note", note, STATUS_VERDICT[status])
    set_status(conn, hypothesis_id, status)
    return status, cells, []


# --- single-symbol ideas (H26-H30) ---------------------------------------------------------

OVERNIGHT_SYMBOLS = ("XLK", "XLV", "XLF", "EEM", "HYG")
CALENDAR_SYMBOLS = ("XLU", "XLP", "XLY", "XLI", "XLB")


def event_net_returns(bars, generate_signals, start, end):
    """Net return of each trade run (entry inside the window), including the exit-day cost."""
    asset = bars["close"].pct_change().fillna(0.0).to_numpy()
    position = _signals(bars, generate_signals).shift(1).fillna(0.0)
    pos = position.to_numpy()
    turnover = np.abs(np.diff(pos, prepend=0.0))
    net = pos * asset - turnover * COST_BPS * BP
    index = bars.index
    lo = index.searchsorted(start) if start else 0
    hi = len(index) if end is None else index.searchsorted(end, side="right")
    events, i = [], 0
    while i < len(pos):
        if pos[i] > 0 and (i == 0 or pos[i - 1] == 0):
            j = i
            while j + 1 < len(pos) and pos[j + 1] > 0:
                j += 1
            if lo <= i < hi:
                events.append(float(net[i:min(j + 2, len(pos))].sum()))
            i = j + 1
        else:
            i += 1
    return events


def cell_tilt(r, x, label, **_):  # H26
    s, b = r["strategy"], r["buy_and_hold"]
    need = 8 if label == "IS" else 4
    if x["derisk_events"] < need:
        return "inconclusive", f"only {x['derisk_events']} de-risk episodes (need {need})"
    fails = []
    if s["sharpe"] < b["sharpe"] + 0.05:
        fails.append(f"Sharpe {s['sharpe']:.2f} < buy&hold {b['sharpe']:.2f} + 0.05")
    if s["cagr"] < b["cagr"] - 0.02:
        fails.append(f"CAGR {s['cagr']:.1%} more than 2pts below {b['cagr']:.1%}")
    if b["sharpe"] <= 0 and s["sharpe"] < 0:
        fails.append(f"Sharpe {s['sharpe']:.2f} below 0 (buy&hold Sharpe is not positive)")
    return ("contradicts", "; ".join(fails)) if fails else ("supports", "passes kill threshold")


def veto_tilt(r, x):
    s, b = r["strategy"], r["buy_and_hold"]
    if s["sharpe"] < b["sharpe"] - 0.20:
        return f"Sharpe {s['sharpe']:.2f} more than 0.20 below buy&hold {b['sharpe']:.2f}"
    if s["cagr"] < b["cagr"] - 0.04:
        return f"CAGR {s['cagr']:.1%} more than 4pts below buy&hold {b['cagr']:.1%}"
    return None


def cell_trend(r, x, label, **_):  # H27
    s, b = r["strategy"], r["buy_and_hold"]
    changes = s["entries"] + s["exits"]
    if changes < 4:
        return "inconclusive", f"only {changes} position changes (need 4)"
    fails = drawdown_rule(r, dd_margin=0.05, sharpe_mult=1.0)
    if s["sharpe"] < 0:
        fails.append(f"Sharpe {s['sharpe']:.2f} below 0")
    if s["cagr"] < b["cagr"] - 0.05:
        fails.append(f"CAGR {s['cagr']:.1%} more than 5pts below {b['cagr']:.1%}")
    return ("contradicts", "; ".join(fails)) if fails else ("supports", "passes kill threshold")


def veto_trend(r, x):
    s, b = r["strategy"], r["buy_and_hold"]
    if s["sharpe"] < b["sharpe"] - 0.30:
        return f"Sharpe {s['sharpe']:.2f} more than 0.30 below buy&hold {b['sharpe']:.2f}"
    return None


def cell_washout(r, x, label, events=()):  # H28
    s, b = r["strategy"], r["buy_and_hold"]
    need = 15 if label == "IS" else 6
    if len(events) < need:
        return "inconclusive", f"only {len(events)} events (need {need})"
    hit = float(np.mean([e > 0 for e in events]))
    fails = []
    if s["return_per_exposure_day"] < b["mean_daily_return"] + 10 * BP:
        fails.append(f"return/exposure day {s['return_per_exposure_day']:.3%} < buy&hold mean "
                     f"{b['mean_daily_return']:.3%} + 10bps")
    if hit < 0.55:
        fails.append(f"hit rate {hit:.0%} < 55%")
    return ("contradicts", "; ".join(fails)) if fails else ("supports", f"passes kill threshold (hit rate {hit:.0%})")


def veto_negative_rped(r, x):
    s = r["strategy"]
    if s["exposure_days"] and s["return_per_exposure_day"] < 0:
        return f"return/exposure day {s['return_per_exposure_day']:.3%} below 0"
    return None


def calendar_cell(abs_floor, margin, sharpe_margin, minimum):
    def rule(r, x, label, **_):
        s, b = r["strategy"], r["buy_and_hold"]
        need = minimum[0] if label == "IS" else minimum[1]
        if s["entries"] < need:
            return "inconclusive", f"only {s['entries']} entries (need {need})"
        fails = []
        if s["return_per_exposure_day"] < b["mean_daily_return"] + margin * BP:
            fails.append(f"return/exposure day {s['return_per_exposure_day']:.3%} < buy&hold mean "
                         f"{b['mean_daily_return']:.3%} + {margin:g}bps")
        if s["return_per_exposure_day"] < abs_floor * BP:
            fails.append(f"return/exposure day {s['return_per_exposure_day']:.3%} < {abs_floor:g}bps absolute")
        if x["cond_sharpe"] < b["sharpe"] + sharpe_margin:
            fails.append(f"conditional Sharpe {x['cond_sharpe']:.2f} < buy&hold {b['sharpe']:.2f} + {sharpe_margin}")
        return ("contradicts", "; ".join(fails)) if fails else ("supports", "passes kill threshold")
    return rule


SINGLE = {
    # id: (file, symbols, cell rule, veto, veto kind, placebo metric, needs event list)
    26: ("overnight_tilt_v1.py", OVERNIGHT_SYMBOLS, cell_tilt, veto_tilt, "block", "sharpe", False),
    27: ("overnight_trend_v1.py", OVERNIGHT_SYMBOLS, cell_trend, veto_trend, "block", "sharpe", False),
    28: ("gap_fade_washout_v1.py", OVERNIGHT_SYMBOLS, cell_washout, veto_negative_rped, "block",
         "return_per_exposure_day", True),
    29: ("halloween_v1.py", CALENDAR_SYMBOLS, calendar_cell(2, 3, 0.10, (7, 3)), None, "calendar",
         "return_per_exposure_day", False),
    30: ("earnings_season_v1.py", CALENDAR_SYMBOLS, calendar_cell(3, 4, 0.15, (24, 12)), None, "calendar",
         "return_per_exposure_day", False),
}


def score_single(hypothesis_id, conn, bars_all):
    filename, symbols, cell_rule, veto_rule, veto_kind, metric, needs_events = SINGLE[hypothesis_id]
    strategy = load_strategy(ROOT / "strategies" / filename)
    set_strategy(conn, hypothesis_id, filename)
    set_status(conn, hypothesis_id, "testing")
    cells, vetoes, control = {}, [], {}
    for symbol in symbols:
        bars = bars_all[symbol]
        for label, (start, end) in WINDOWS.items():
            result = run_backtest(bars, strategy.generate_signals, COST_BPS, start, end)
            path = save_result(result, strategy, symbol, window=f"{result['start']}_{result['end']}")
            x = extras(bars, strategy.generate_signals, start, end)
            events = event_net_returns(bars, strategy.generate_signals, start, end) if needs_events else ()
            verdict, why = cell_rule(result, x, label, events=events)
            if veto_rule:
                veto = veto_rule(result, x)
                if veto:
                    vetoes.append(f"{symbol} {label}: {veto}")
            if hypothesis_id == 27:       # diagnostic control: the same rule on close-to-close returns
                ctl = run_backtest(bars, lambda b: strategy.generate_signals(b, component="close"),
                                   COST_BPS, start, end)
                control[(symbol, label)] = cell_rule(ctl, extras(
                    bars, lambda b: strategy.generate_signals(b, component="close"), start, end), label)[0]
            s, b = result["strategy"], result["buy_and_hold"]
            summary = (f"{filename[:-3]} {symbol} {label} {result['start']}..{result['end']}, 5 bps: "
                       f"Sharpe {s['sharpe']:.2f} vs {b['sharpe']:.2f}, MaxDD {s['max_drawdown']:.1%} vs "
                       f"{b['max_drawdown']:.1%}, CAGR {s['cagr']:.1%} vs {b['cagr']:.1%}, exposure "
                       f"{s['exposure']:.0%}, {s['entries']} entries/{s['exits']} exits, return/exposure day "
                       f"{s['return_per_exposure_day']:.3%} vs buy&hold mean {b['mean_daily_return']:.3%}, "
                       f"conditional Sharpe {x['cond_sharpe']:.2f}. {verdict}: {why}")
            add_evidence(conn, hypothesis_id, "backtest", summary, verdict, ref=str(path.relative_to(ROOT)))
            cells[(symbol, label)] = {"result": result, "extras": x, "verdict": verdict, "why": why,
                                      "ref": str(path.relative_to(ROOT)), "events": len(events)}

    by_symbol = {sym: {w: cells[(sym, w)]["verdict"] for w in WINDOWS} for sym in symbols}
    status = symbol_status(by_symbol, min_symbols=4)
    notes = []
    if veto_kind == "calendar":
        for label in WINDOWS:
            weak = [sym for sym in symbols
                    if cells[(sym, label)]["result"]["strategy"]["return_per_exposure_day"]
                    < cells[(sym, label)]["result"]["buy_and_hold"]["mean_daily_return"] - 5 * BP]
            if len(weak) >= 3:
                status = "rejected"
                notes.append(f"hard veto: {label} has {len(weak)} symbols ({', '.join(weak)}) with return/exposure "
                             f"day below buy&hold mean - 5bps")
                break
    elif vetoes and status == "supported":
        status = "testing"
        notes.append("veto blocks SUPPORTED: " + "; ".join(vetoes))
    elif vetoes:
        notes.append("veto also fires: " + "; ".join(vetoes))

    placebo = None
    if status == "supported":
        values = []
        for (symbol, label), cell in cells.items():
            if cell["verdict"] != "supports":
                continue
            start, end = WINDOWS[label]
            asset, position = window_arrays(bars_all[symbol], strategy.generate_signals, start, end)
            values.append(placebo_percentile(asset, position, COST_BPS, metric, PLACEBO["n"],
                                             PLACEBO["seed"], PLACEBO["min_shift"]))
        placebo = float(np.mean(values))
        if placebo < PLACEBO["threshold"]:
            status = "testing"
            notes.append(f"all cell rules pass but mean placebo percentile {placebo:.2f} < 0.95")
        else:
            notes.append(f"mean placebo percentile {placebo:.2f} >= 0.95")
    if hypothesis_id == 27:
        passed = [f"{k[0]} {k[1]}" for k, v in control.items() if v == "supports"]
        notes.append("close-to-close control would support: " + (", ".join(passed) or "no cell"))

    passing = sum(c["verdict"] == "supports" for c in cells.values())
    symbols_passing = sum(all(v == "supports" for v in w.values()) for w in by_symbol.values())
    note = (f"Round-3 verdict: {status} ({passing}/10 cells and {symbols_passing}/5 symbols pass the "
            f"pre-set kill rule; need 4 symbols and placebo >= 0.95)." + (" " + " ".join(notes) if notes else ""))
    add_evidence(conn, hypothesis_id, "note", note, STATUS_VERDICT[status])
    set_status(conn, hypothesis_id, status)
    return status, cells, notes, placebo


def main():
    names = {s for _, symbols, *_ in SINGLE.values() for s in symbols}
    portfolio_names = {"SPY", "QQQ", "IWM", "EFA", "EEM", "VNQ", "DBC", "GLD", "TLT", "HYG", "LQD", "IEF",
                       "AGG", "BIL", "XLE", "XLK", "XLV", "XLF", "XLU", "XLP", "XLY", "XLI", "XLB"}
    bars_all = {s: load_bars(s) for s in sorted(names | portfolio_names)}
    conn = connect()
    summary = {"reading_notes": READING_NOTES, "hypotheses": {}}

    for hid in PORTFOLIO:
        status, cells, notes = score_portfolio(hid, conn, bars_all)
        print(f"H{hid} {PORTFOLIO[hid]}: {status}")
        rows = []
        for (universe, label), c in cells.items():
            s, bm = c["result"]["strategy"], c["result"]["benchmarks"]
            e = bm["equal_weight_monthly"]
            print(f"  {universe:9s} {label:3s} Sharpe {s['sharpe']:5.2f} (eq-wt {e['sharpe']:5.2f}, best "
                  f"{max(m['sharpe'] for m in bm.values()):5.2f}) MaxDD {s['max_drawdown']:6.1%}/{e['max_drawdown']:6.1%} "
                  f"CAGR {s['cagr']:6.1%}/{e['cagr']:6.1%} trades {s['trades']:3d} placebo {c['placebo']:.2f} "
                  f"-> {c['verdict']}: {c['why']}")
            rows.append({"cell": f"{universe} {label}", "verdict": c["verdict"], "why": c["why"],
                         "ref": c["ref"], "placebo": c["placebo"], "strategy": s, "benchmarks": bm})
        summary["hypotheses"][hid] = {"status": status, "notes": notes, "cells": rows}

    for hid in SINGLE:
        status, cells, notes, placebo = score_single(hid, conn, bars_all)
        print(f"H{hid} {SINGLE[hid][0]}: {status}" + (f"  [{' '.join(notes)}]" if notes else ""))
        rows = []
        for (symbol, label), c in cells.items():
            s, b, x = c["result"]["strategy"], c["result"]["buy_and_hold"], c["extras"]
            print(f"  {symbol} {label:3s} Sharpe {s['sharpe']:5.2f}/{b['sharpe']:5.2f} CAGR {s['cagr']:6.1%}/{b['cagr']:6.1%} "
                  f"MaxDD {s['max_drawdown']:6.1%}/{b['max_drawdown']:6.1%} rped {s['return_per_exposure_day']:7.3%}/"
                  f"{b['mean_daily_return']:7.3%} cond {x['cond_sharpe']:5.2f} exp {s['exposure']:4.0%} "
                  f"ent {s['entries']:3d} ev {x['derisk_events']:3d} -> {c['verdict']}: {c['why']}")
            rows.append({"symbol": symbol, "window": label, "verdict": c["verdict"], "why": c["why"],
                         "ref": c["ref"], "strategy": s, "buy_and_hold": b, "extras": x, "events": c["events"]})
        summary["hypotheses"][hid] = {"status": status, "notes": notes, "placebo_mean_percentile": placebo,
                                      "cells": rows}
    conn.close()
    out = ROOT / "backtests" / "round3_summary.json"
    out.write_text(json.dumps(summary, indent=2) + "\n")
    print(f"wrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
