"""Score hypotheses 14-22 against the kill rules fixed in their 2026-10-12 round-2 memos.

    PYTHONPATH=. python research/round2_verdicts.py

For each hypothesis, 5 symbols x 2 windows (IS 2016-01-01..2022-12-31, OOS 2023-01-01..end) at
5 bps: runs the backtest on full-history signals, saves it under backtests/, and logs one evidence
row per cell plus a summary note. Final status:
  rejected  - a stated veto fires, or too many cells fail for 4/5 symbols to pass
  testing   - nothing decisive: inconclusive cells could still change the outcome, a stated
              "untestable" condition holds, or all cell rules pass but the placebo does not
  supported - >= 4 of 5 symbols pass both windows, extra memo conditions hold, and the mean placebo
              percentile over passing cells is >= 0.95
The rules below are transcribed from the memos; they were not changed after seeing results.
Reading choices where a memo is silent are listed in READING_NOTES and in the PR.
"""

import json
import math

import numpy as np

from core.backtest import TRADING_DAYS, _signals, load_strategy, run_backtest, save_result
from core.config import ROOT
from core.data import load_bars
from core.ledger import add_evidence, connect, set_status, set_strategy
from core.verdicts import drawdown_rule, placebo_percentile, symbol_status, window_arrays

SYMBOLS = ("IWM", "TLT", "GLD", "XLE", "EFA")
WINDOWS = {"IS": ("2016-01-01", "2022-12-31"), "OOS": ("2023-01-01", None)}
COST_BPS = 5.0
PLACEBO = {"n": 1000, "seed": 0, "min_shift": 252, "threshold": 0.95}
BP = 1e-4

READING_NOTES = [
    "A veto applies to every cell with a position, including inconclusive cells ('any cell').",
    "A hypothesis whose cells all pass but whose mean placebo percentile is < 0.95 is left "
    "'testing' (not supported), since the memos only say it is not SUPPORTED.",
    "H14-16 'de-risk event' = a day-on-day position drop of at least 0.25 inside the window.",
    "H18 uses the population std (ddof=0) for z50, as H17's memo specifies for z20.",
    "Exit bars stay flat (no same-bar re-entry) for H18, H19, H21, H22.",
]


def extras(bars, generate_signals, start, end):
    """Metrics the backtester does not report: conditional Sharpe, de-risk events, time below 1."""
    asset = bars["close"].pct_change().fillna(0.0)
    position = _signals(bars, generate_signals).shift(1).fillna(0.0)
    turnover = position.diff().abs().fillna(position.abs())
    net = position * asset - turnover * COST_BPS * BP
    window = slice(start, end)
    net, pos, drops = net.loc[window], position.loc[window], position.diff().loc[window]
    held = net[pos > 0]
    cond = float(held.mean() / held.std() * math.sqrt(TRADING_DAYS)) if len(held) > 2 and held.std() > 0 else 0.0
    return {
        "cond_sharpe": cond,
        "derisk_events": int((drops <= -0.25 + 1e-9).sum()),
        "frac_below_1": float((pos < 1).mean()),
    }


# --- per-hypothesis rules: cell(r, x, label) -> (verdict, why); veto(r, x) -> reason or None ------

def _result(verdict, fails, ok="passes kill threshold"):
    return ("contradicts", "; ".join(fails)) if fails else (verdict, ok)


def cell_drawdown_family(r, x, label):  # H14, H15, H16
    b = r["buy_and_hold"]
    need = 3 if label == "IS" else 2
    if x["derisk_events"] < need:
        return "inconclusive", f"only {x['derisk_events']} de-risk events (need {need})"
    margin = min(0.05, 0.25 * abs(b["max_drawdown"]))
    return _result("supports", drawdown_rule(r, dd_margin=margin, sharpe_mult=1.0))


def veto_drawdown_family(r, x):
    s, b = r["strategy"], r["buy_and_hold"]
    if s["sharpe"] < b["sharpe"] - 0.15:
        return f"Sharpe {s['sharpe']:.2f} more than 0.15 below buy&hold {b['sharpe']:.2f}"
    if s["max_drawdown"] < b["max_drawdown"] - 0.02:
        return f"MaxDD {s['max_drawdown']:.1%} more than 2pts deeper than {b['max_drawdown']:.1%}"
    return None


def cell_bollinger(r, x, label):  # H17
    s, b = r["strategy"], r["buy_and_hold"]
    need = 15 if label == "IS" else 8
    if s["exits"] < need:
        return "inconclusive", f"only {s['exits']} step-asides (need {need})"
    fails = []
    if s["sharpe"] < b["sharpe"] + 0.10:
        fails.append(f"Sharpe {s['sharpe']:.2f} < buy&hold {b['sharpe']:.2f} + 0.10")
    if s["max_drawdown"] < b["max_drawdown"]:
        fails.append(f"MaxDD {s['max_drawdown']:.1%} worse than {b['max_drawdown']:.1%}")
    if s["return_per_exposure_day"] < b["mean_daily_return"] + 1 * BP:
        fails.append(f"return/exposure day {s['return_per_exposure_day']:.3%} < buy&hold mean "
                     f"{b['mean_daily_return']:.3%} + 1bp")
    return _result("supports", fails)


def veto_bollinger(r, x):
    s, b = r["strategy"], r["buy_and_hold"]
    if s["max_drawdown"] < b["max_drawdown"] - 0.05:
        return f"MaxDD {s['max_drawdown']:.1%} more than 5pts worse than {b['max_drawdown']:.1%}"
    return None


def cell_part_time(minimum):  # H18, H19: (IS entries, OOS entries)
    def rule(r, x, label):
        s, b = r["strategy"], r["buy_and_hold"]
        need = minimum[0] if label == "IS" else minimum[1]
        if s["entries"] < need:
            return "inconclusive", f"only {s['entries']} entries (need {need})"
        fails = []
        if s["return_per_exposure_day"] < b["mean_daily_return"] + 5 * BP:
            fails.append(f"return/exposure day {s['return_per_exposure_day']:.3%} < buy&hold mean "
                         f"{b['mean_daily_return']:.3%} + 5bps")
        if x["cond_sharpe"] < b["sharpe"] + 0.25:
            fails.append(f"conditional Sharpe {x['cond_sharpe']:.2f} < buy&hold {b['sharpe']:.2f} + 0.25")
        if s["sharpe"] < b["sharpe"] - 0.10:
            fails.append(f"Sharpe {s['sharpe']:.2f} < buy&hold {b['sharpe']:.2f} - 0.10")
        return _result("supports", fails)
    return rule


def veto_part_time(r, x):
    s = r["strategy"]
    if s["exposure_days"] and s["return_per_exposure_day"] < -5 * BP:
        return f"return/exposure day {s['return_per_exposure_day']:.3%} below -5bps"
    return None


def cell_good_bad_vol(r, x, label):  # H20
    s, b = r["strategy"], r["buy_and_hold"]
    need = 6 if label == "IS" else 3
    if b["sharpe"] < 0.20:
        return "inconclusive", f"buy&hold Sharpe {b['sharpe']:.2f} < 0.20 (nothing to protect)"
    if s["exits"] < need:
        return "inconclusive", f"only {s['exits']} exits (need {need})"
    fails = drawdown_rule(r, dd_margin=0.05, sharpe_mult=1.0)
    if s["sharpe"] < b["sharpe"] + 0.05:
        fails.append(f"Sharpe {s['sharpe']:.2f} < buy&hold {b['sharpe']:.2f} + 0.05")
    return _result("supports", fails)


def veto_good_bad_vol(r, x):
    s, b = r["strategy"], r["buy_and_hold"]
    if s["sharpe"] < b["sharpe"] - 0.15:
        return f"Sharpe {s['sharpe']:.2f} more than 0.15 below buy&hold {b['sharpe']:.2f}"
    return None


def cell_squeeze(r, x, label):  # H21
    s, b = r["strategy"], r["buy_and_hold"]
    need = 10 if label == "IS" else 4
    if s["entries"] < need:
        return "inconclusive", f"only {s['entries']} entries (need {need})"
    fails = []
    if s["return_per_exposure_day"] < 3 * BP:
        fails.append(f"return/exposure day {s['return_per_exposure_day']:.3%} < 3bps")
    if s["return_per_exposure_day"] < b["mean_daily_return"] + 3 * BP:
        fails.append(f"return/exposure day {s['return_per_exposure_day']:.3%} < buy&hold mean "
                     f"{b['mean_daily_return']:.3%} + 3bps")
    if x["cond_sharpe"] < b["sharpe"] + 0.10:
        fails.append(f"conditional Sharpe {x['cond_sharpe']:.2f} < buy&hold {b['sharpe']:.2f} + 0.10")
    if s["exposure"] < 0.03:
        fails.append(f"exposure {s['exposure']:.1%} < 3% (too sparse to matter)")
    return _result("supports", fails)


def cell_rebound(r, x, label):  # H22
    s, b = r["strategy"], r["buy_and_hold"]
    if s["entries"] < 4:
        return "inconclusive", f"only {s['entries']} entries (need 4)"
    fails = []
    if s["return_per_exposure_day"] < b["mean_daily_return"] + 5 * BP:
        fails.append(f"return/exposure day {s['return_per_exposure_day']:.3%} < buy&hold mean "
                     f"{b['mean_daily_return']:.3%} + 5bps")
    if x["cond_sharpe"] < b["sharpe"]:
        fails.append(f"conditional Sharpe {x['cond_sharpe']:.2f} < buy&hold {b['sharpe']:.2f}")
    return _result("supports", fails)


def veto_negative_edge(r, x):
    s = r["strategy"]
    if s["exposure_days"] and s["return_per_exposure_day"] < 0:
        return f"return/exposure day {s['return_per_exposure_day']:.3%} below 0"
    return None


HYPOTHESES = {
    # id: (strategy file, cell rule, veto, placebo metric)
    14: ("dd_gated_sma_exit_v1.py", cell_drawdown_family, veto_drawdown_family, "sharpe"),
    15: ("trend_vol_throttle_v1.py", cell_drawdown_family, veto_drawdown_family, "sharpe"),
    16: ("cppi_cushion_v1.py", cell_drawdown_family, veto_drawdown_family, "sharpe"),
    17: ("bollinger_stepaside_v1.py", cell_bollinger, veto_bollinger, "sharpe"),
    18: ("mean_reversion_z50_v1.py", cell_part_time((12, 6)), veto_part_time, "return_per_exposure_day"),
    19: ("volume_shock_reversal_v1.py", cell_part_time((20, 10)), veto_part_time, "return_per_exposure_day"),
    20: ("good_bad_vol_filter_v1.py", cell_good_bad_vol, veto_good_bad_vol, "sharpe"),
    21: ("squeeze_release_v1.py", cell_squeeze, veto_negative_edge, "return_per_exposure_day"),
    22: ("vol_peak_rebound_v1.py", cell_rebound, veto_negative_edge, "return_per_exposure_day"),
}


def extra_conditions(hypothesis_id, cells):
    """Memo conditions beyond the cell rule. Returns (status override or None, notes)."""
    notes = []
    if hypothesis_id in (14, 15, 16):
        # at least 3 passing symbols must have buy-and-hold Sharpe > 0 in both windows
        passing = [sym for sym in SYMBOLS
                   if all(cells[(sym, w)]["verdict"] == "supports" for w in WINDOWS)]
        positive = [sym for sym in passing
                    if all(cells[(sym, w)]["result"]["buy_and_hold"]["sharpe"] > 0 for w in WINDOWS)]
        if len(passing) >= 4 and len(positive) < 3:
            return "rejected", [f"only {len(positive)} passing symbols have buy&hold Sharpe > 0 in both windows"]
    if hypothesis_id == 14:
        noop = sum(c["extras"]["frac_below_1"] < 0.05 for c in cells.values())
        if noop >= 3:
            return "testing", [f"filter is a no-op (weight < 1 on under 5% of days) in {noop} cells: untestable"]
    if hypothesis_id == 16:
        for label in WINDOWS:
            in_window = [cells[(sym, label)] for sym in SYMBOLS]
            tight = np.mean([c["extras"]["frac_below_1"] for c in in_window]) > 0.40
            behind = sum(c["result"]["strategy"]["sharpe"] < c["result"]["buy_and_hold"]["sharpe"]
                         for c in in_window)
            if tight and behind >= 3:
                return "rejected", [f"{label}: cushion too tight (mean time below weight 1 above 40%, "
                                    f"Sharpe below buy&hold on {behind} symbols)"]
    return None, notes


def score(hypothesis_id, conn, bars):
    filename, cell_rule, veto_rule, metric = HYPOTHESES[hypothesis_id]
    strategy = load_strategy(ROOT / "strategies" / filename)
    set_strategy(conn, hypothesis_id, filename)
    set_status(conn, hypothesis_id, "testing")

    cells, vetoes = {}, []
    for symbol in SYMBOLS:
        for label, (start, end) in WINDOWS.items():
            result = run_backtest(bars[symbol], strategy.generate_signals, COST_BPS, start, end)
            path = save_result(result, strategy, symbol, window=f"{result['start']}_{result['end']}")
            x = extras(bars[symbol], strategy.generate_signals, start, end)
            verdict, why = cell_rule(result, x, label)
            veto = veto_rule(result, x)
            if veto:
                vetoes.append(f"{symbol} {label}: {veto}")
            s, b = result["strategy"], result["buy_and_hold"]
            summary = (f"{filename[:-3]} {symbol} {label} {result['start']}..{result['end']}, 5 bps: "
                       f"Sharpe {s['sharpe']:.2f} vs {b['sharpe']:.2f}, MaxDD {s['max_drawdown']:.1%} vs "
                       f"{b['max_drawdown']:.1%}, CAGR {s['cagr']:.1%} vs {b['cagr']:.1%}, exposure "
                       f"{s['exposure']:.0%}, {s['entries']} entries/{s['exits']} exits, return/exposure "
                       f"day {s['return_per_exposure_day']:.3%} vs buy&hold mean {b['mean_daily_return']:.3%}, "
                       f"conditional Sharpe {x['cond_sharpe']:.2f}. {verdict}: {why}")
            add_evidence(conn, hypothesis_id, "backtest", summary, verdict, ref=str(path.relative_to(ROOT)))
            cells[(symbol, label)] = {"result": result, "extras": x, "verdict": verdict, "why": why,
                                      "ref": str(path.relative_to(ROOT))}

    by_symbol = {sym: {w: cells[(sym, w)]["verdict"] for w in WINDOWS} for sym in SYMBOLS}
    status = symbol_status(by_symbol, min_symbols=4)
    notes = []
    if vetoes:
        status, notes = "rejected", ["veto: " + "; ".join(vetoes)]
    else:
        override, extra_notes = extra_conditions(hypothesis_id, cells)
        if override:
            status, notes = override, extra_notes

    placebo = None
    if status == "supported":
        percentiles = []
        for key, cell in cells.items():
            if cell["verdict"] != "supports":
                continue
            start, end = WINDOWS[key[1]]
            asset, position = window_arrays(bars[key[0]], strategy.generate_signals, start, end)
            percentiles.append(placebo_percentile(asset, position, COST_BPS, metric, PLACEBO["n"],
                                                  PLACEBO["seed"], PLACEBO["min_shift"]))
        placebo = float(np.mean(percentiles))
        if placebo < PLACEBO["threshold"]:
            status = "testing"
            notes.append(f"all cell rules pass but mean placebo percentile {placebo:.2f} < 0.95")
        else:
            notes.append(f"mean placebo percentile {placebo:.2f} >= 0.95")

    passing = sum(c["verdict"] == "supports" for c in cells.values())
    symbols_passing = sum(all(v == "supports" for v in w.values()) for w in by_symbol.values())
    note = (f"Round-2 verdict: {status} ({passing}/10 cells and {symbols_passing}/5 symbols pass the "
            f"pre-set kill rule; need 4 symbols and placebo >= 0.95)." + (" " + " ".join(notes) if notes else ""))
    add_evidence(conn, hypothesis_id, "note", note, {"rejected": "contradicts", "testing": "inconclusive",
                                                     "supported": "supports"}[status])
    set_status(conn, hypothesis_id, status)
    return status, cells, notes, placebo


def main():
    bars = {symbol: load_bars(symbol) for symbol in SYMBOLS}
    conn = connect()
    summary = {"reading_notes": READING_NOTES, "hypotheses": {}}
    for hypothesis_id in HYPOTHESES:
        status, cells, notes, placebo = score(hypothesis_id, conn, bars)
        print(f"H{hypothesis_id} {HYPOTHESES[hypothesis_id][0]}: {status}"
              + (f"  [{' '.join(notes)}]" if notes else ""))
        rows = []
        for (symbol, label), c in cells.items():
            s, b, x = c["result"]["strategy"], c["result"]["buy_and_hold"], c["extras"]
            print(f"  {symbol} {label:3s} Sharpe {s['sharpe']:5.2f}/{b['sharpe']:5.2f} "
                  f"MaxDD {s['max_drawdown']:6.1%}/{b['max_drawdown']:6.1%} "
                  f"rped {s['return_per_exposure_day']:7.3%}/{b['mean_daily_return']:7.3%} "
                  f"cond {x['cond_sharpe']:5.2f} exp {s['exposure']:4.0%} "
                  f"ent {s['entries']:3d} ex {s['exits']:3d} ev {x['derisk_events']:3d} -> {c['verdict']}: {c['why']}")
            rows.append({"symbol": symbol, "window": label, "verdict": c["verdict"], "why": c["why"],
                         "ref": c["ref"], "strategy": s, "buy_and_hold": b, "extras": x})
        summary["hypotheses"][hypothesis_id] = {"status": status, "notes": notes,
                                                "placebo_mean_percentile": placebo, "cells": rows}
    conn.close()
    out = ROOT / "backtests" / "round2_summary.json"
    out.write_text(json.dumps(summary, indent=2) + "\n")
    print(f"wrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
