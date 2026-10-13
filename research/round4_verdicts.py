"""Score hypotheses 31-32 against the rules fixed in research/r4-month-end-flows-2026-10-13.md.

    PYTHONPATH=. python research/round4_verdicts.py

H31 (month-end Treasury bid) is a single-symbol rule scored per ETF; H32 (pension rebalancing
tilt) is a two-asset overlay scored per universe against its untilted monthly 60/40. Windows:
IS 2016-01-01..2022-12-31, OOS 2023-01-01..end of data, 5 bps per unit of turnover. Every cell is
saved under backtests/ and logged in the ledger; the rules (including the delayed-fill check and,
for H32, the month-level sign-shuffle placebo) were fixed in the memo before any code was written.
"""

import json

import numpy as np
import pandas as pd

from core.backtest import TRADING_DAYS, load_strategy, run_backtest, save_result
from core.config import ROOT
from core.data import load_bars
from core.ledger import add_evidence, connect, set_status, set_strategy
from core.portfolio import (load_portfolio_strategy, month_ends, prepare, run_portfolio_backtest,
                            simulate, targets_from)
from core.verdicts import placebo_percentile, symbol_status, window_arrays
from research.round3_verdicts import event_net_returns

WINDOWS = {"IS": ("2016-01-01", "2022-12-31"), "OOS": ("2023-01-01", None)}
COST_BPS = 5.0
BP = 1e-4
PLACEBO = {"n": 1000, "seed": 0, "min_shift": 252, "threshold": 0.95}
STATUS_VERDICT = {"rejected": "contradicts", "testing": "inconclusive", "supported": "supports"}
HYPOTHESES_TESTED = 32


# --- H31: month-end Treasury bid ------------------------------------------------------------

TREASURIES = ("VGLT", "SPTL", "EDV", "ZROZ", "TLH")


def delayed_signals(generate_signals):
    """Every target one trading day late: decided at close t, traded at close t+1."""
    return lambda bars: generate_signals(bars).shift(1).fillna(0.0)


def score_h31(conn, bars_all):
    strategy = load_strategy(ROOT / "strategies" / "treasury_month_end_v1.py")
    gen, late = strategy.generate_signals, delayed_signals(strategy.generate_signals)
    set_strategy(conn, 31, "treasury_month_end_v1.py")
    set_status(conn, 31, "testing")
    cells, rows = {}, []
    for symbol in TREASURIES:
        bars = bars_all[symbol]
        for label, (start, end) in WINDOWS.items():
            r = run_backtest(bars, gen, COST_BPS, start, end)
            path = save_result(r, strategy, symbol, window=f"{r['start']}_{r['end']}")
            events = event_net_returns(bars, gen, start, end)
            late_events = event_net_returns(bars, late, start, end)
            asset, position = window_arrays(bars, gen, start, end)
            pct = placebo_percentile(asset, position, COST_BPS, "return_per_exposure_day", PLACEBO["n"],
                                     PLACEBO["seed"], PLACEBO["min_shift"])
            # secondary line, not scored: hold BIL instead of cash when out
            both = {symbol: bars, "BIL": bars_all["BIL"]}
            bil = run_portfolio_backtest(both, lambda b, s=symbol: pd.DataFrame(
                {s: gen(b[s]), "BIL": 1.0 - gen(b[s])}), COST_BPS, start, end)["strategy"]
            s, b = r["strategy"], r["buy_and_hold"]
            mean_event = float(np.mean(events)) if events else 0.0
            mean_late = float(np.mean(late_events)) if late_events else 0.0
            need = 60 if label == "IS" else 36
            if len(events) < need:
                verdict, why = "inconclusive", f"only {len(events)} events (need {need})"
            else:
                fails = []
                if mean_event < 10 * BP:
                    fails.append(f"mean net per event {mean_event:.3%} < 10bps")
                if s["return_per_exposure_day"] < b["mean_daily_return"] + 5 * BP:
                    fails.append(f"return/exposure day {s['return_per_exposure_day']:.3%} < buy&hold mean "
                                 f"{b['mean_daily_return']:.3%} + 5bps")
                if pct < PLACEBO["threshold"]:
                    fails.append(f"placebo percentile {pct:.2f} < 0.95")
                if mean_late <= 0:
                    fails.append(f"delayed-fill mean per event {mean_late:.3%} not above 0")
                verdict, why = ("contradicts", "; ".join(fails)) if fails else ("supports", "passes kill rule")
            summary = (f"treasury_month_end_v1 {symbol} {label} {r['start']}..{r['end']}, 5 bps: {len(events)} events, "
                       f"mean net per event {mean_event:.3%} (delayed fill {mean_late:.3%}), hit rate "
                       f"{np.mean([e > 0 for e in events]) if events else 0:.0%}, return/exposure day "
                       f"{s['return_per_exposure_day']:.3%} vs buy&hold mean {b['mean_daily_return']:.3%}, placebo "
                       f"{pct:.2f}; Sharpe {s['sharpe']:.2f} vs {b['sharpe']:.2f}, exposure {s['exposure']:.0%}. "
                       f"BIL variant (not scored): CAGR {bil['cagr']:.1%}, Sharpe {bil['sharpe']:.2f}. {verdict}: {why}")
            add_evidence(conn, 31, "backtest", summary, verdict, ref=str(path.relative_to(ROOT)))
            cells[(symbol, label)] = verdict
            rows.append({"symbol": symbol, "window": label, "verdict": verdict, "why": why,
                         "ref": str(path.relative_to(ROOT)), "events": len(events), "mean_event": mean_event,
                         "mean_event_delayed": mean_late, "hit_rate": float(np.mean([e > 0 for e in events])) if events else 0.0,
                         "placebo": pct, "strategy": s, "buy_and_hold": b,
                         "bil_variant": {"cagr": bil["cagr"], "sharpe": bil["sharpe"], "max_drawdown": bil["max_drawdown"]}})
    by_symbol = {sym: {w: cells[(sym, w)] for w in WINDOWS} for sym in TREASURIES}
    status = symbol_status(by_symbol, min_symbols=4)
    passing = sum(v == "supports" for v in cells.values())
    symbols_passing = sum(all(v == "supports" for v in w.values()) for w in by_symbol.values())
    note = (f"Round-4 verdict: {status} ({passing}/10 cells, {symbols_passing}/5 ETFs pass both windows; need 4). "
            f"Hypotheses tested so far: {HYPOTHESES_TESTED}. The five ETFs are near-duplicates, so this is close to one test.")
    add_evidence(conn, 31, "note", note, STATUS_VERDICT[status])
    set_status(conn, 31, status)
    return status, rows, note


# --- H32: pension rebalancing tilt ----------------------------------------------------------

def active_equity_weight(targets: pd.DataFrame, equity: str, base: float) -> pd.Series:
    """Active equity weight held over each day (target decided at the previous close, minus base)."""
    return (targets[equity].ffill().fillna(base) - base).shift(1).fillna(0.0)


def signed_events(active: pd.Series, spread: pd.Series, start, end) -> list[float]:
    """Per month with a tilt: sum over tilted days of sign(active) x (equity - bond return)."""
    signed = np.sign(active) * spread
    window = slice(start, end)
    a, s = active.loc[window], signed.loc[window]
    months = a.index.to_period("M")
    return [float(s[(months == m) & (a != 0)].sum()) for m in pd.unique(months[a != 0])]


def overlay_placebos(active, spread, cost, start, end):
    """Percentiles of the annualized active return against (a) circular shifts, (b) monthly sign flips."""
    window = slice(start, end)
    a, sp, c = active.loc[window].to_numpy(), spread.loc[window].to_numpy(), cost.loc[window].to_numpy()
    months = active.loc[window].index.to_period("M")
    stat = lambda w, k: float((w * sp - k).mean() * TRADING_DAYS)
    actual = stat(a, c)
    rng = np.random.default_rng(PLACEBO["seed"])
    shifts = rng.integers(PLACEBO["min_shift"], len(a) - PLACEBO["min_shift"] + 1, size=PLACEBO["n"])
    shifted = np.array([stat(np.roll(a, k), np.roll(c, k)) for k in shifts])
    month_codes = pd.factorize(months)[0]
    rng = np.random.default_rng(PLACEBO["seed"])
    flips = rng.choice([-1.0, 1.0], size=(PLACEBO["n"], month_codes.max() + 1))
    shuffled = np.array([stat(a * f[month_codes], c) for f in flips])
    return actual, float((shifted < actual).mean()), float((shuffled < actual).mean())


def score_h32(conn, bars_all):
    module = load_portfolio_strategy(ROOT / "strategies" / "pension_tilt_v1.py")
    base = module.PARAMS["base"]
    set_strategy(conn, 32, "pension_tilt_v1.py")
    set_status(conn, 32, "testing")
    cells, rows = {}, []
    for name, u in module.UNIVERSES.items():
        equity, bond = u["equity"], u["bond"]
        bars = {equity: bars_all[equity], bond: bars_all[bond]}
        gen = lambda b, e=equity, d=bond: module.generate_weights(b, equity=e, bond=d)
        late = lambda b, g=gen: g(b).shift(1)
        aligned, close, run = prepare(bars, gen, COST_BPS)
        bench_targets = pd.DataFrame(np.nan, close.index, close.columns)
        rows_mask = month_ends(close.index)
        rows_mask[0] = True
        bench_targets.loc[rows_mask, equity], bench_targets.loc[rows_mask, bond] = base, 1 - base
        bench = simulate(close, bench_targets, COST_BPS)
        ret = close.pct_change().fillna(0.0)
        spread = ret[equity] - ret[bond]
        # tilt days and their direction come from the targets; the placebo statistic uses the held
        # weights, so (held - benchmark held) x spread - extra cost is exactly the daily net active return
        active = active_equity_weight(targets_from(aligned, gen), equity, base)
        active_late = active_equity_weight(targets_from(aligned, late), equity, base)
        active_held = run["weights"][equity] - bench["weights"][equity]
        cost = (run["traded"] - bench["traded"]) * COST_BPS * BP
        for label, (start, end) in WINDOWS.items():
            window = slice(start, end)
            result = run_portfolio_backtest(bars, gen, COST_BPS, start, end)
            path = save_result(result, module, name, window=f"{result['start']}_{result['end']}")
            events = signed_events(active, spread, start, end)
            late_events = signed_events(active_late, spread, start, end)
            net_active = float((run["returns"] - bench["returns"]).loc[window].mean() * TRADING_DAYS)
            placebo_actual, pct_shift, pct_shuffle = overlay_placebos(active_held, spread, cost, start, end)
            assert abs(placebo_actual - net_active) < 1e-9, (placebo_actual, net_active)
            mean_event = float(np.mean(events)) if events else 0.0
            mean_late = float(np.mean(late_events)) if late_events else 0.0
            need = 30 if label == "IS" else 15
            if len(events) < need:
                verdict, why = "inconclusive", f"only {len(events)} events (need {need})"
            else:
                fails = []
                if mean_event < 20 * BP:
                    fails.append(f"mean signed return per event {mean_event:.3%} < 20bps")
                if net_active <= 0:
                    fails.append(f"net active return {net_active:.2%}/yr not above 0")
                if pct_shift < PLACEBO["threshold"]:
                    fails.append(f"shift placebo {pct_shift:.2f} < 0.95")
                if pct_shuffle < PLACEBO["threshold"]:
                    fails.append(f"sign-shuffle placebo {pct_shuffle:.2f} < 0.95")
                if mean_late <= 0:
                    fails.append(f"delayed-fill mean per event {mean_late:.3%} not above 0")
                verdict, why = ("contradicts", "; ".join(fails)) if fails else ("supports", "passes kill rule")
            strat = result["strategy"]
            bench_window = bench["returns"].loc[window]
            bench_sharpe = float(bench_window.mean() / bench_window.std() * np.sqrt(TRADING_DAYS))
            summary = (f"pension_tilt_v1 {name} {label} {result['start']}..{result['end']}, 5 bps: {len(events)} events, "
                       f"mean signed per event {mean_event:.3%} (delayed fill {mean_late:.3%}), hit rate "
                       f"{np.mean([e > 0 for e in events]) if events else 0:.0%}, net active {net_active:.2%}/yr, "
                       f"placebos shift {pct_shift:.2f} / sign-shuffle {pct_shuffle:.2f}; Sharpe {strat['sharpe']:.2f} vs "
                       f"60/40 {bench_sharpe:.2f}. {verdict}: {why}")
            add_evidence(conn, 32, "backtest", summary, verdict, ref=str(path.relative_to(ROOT)))
            cells[(name, label)] = verdict
            rows.append({"universe": name, "window": label, "verdict": verdict, "why": why,
                         "ref": str(path.relative_to(ROOT)), "events": len(events), "mean_event": mean_event,
                         "mean_event_delayed": mean_late,
                         "hit_rate": float(np.mean([e > 0 for e in events])) if events else 0.0,
                         "net_active": net_active, "placebo_shift": pct_shift, "placebo_shuffle": pct_shuffle,
                         "strategy_sharpe": strat["sharpe"], "benchmark_sharpe": bench_sharpe})
    verdicts = set(cells.values())
    status = ("supported" if verdicts == {"supports"} else "rejected" if "contradicts" in verdicts else "testing")
    passing = sum(v == "supports" for v in cells.values())
    note = (f"Round-4 verdict: {status} ({passing}/6 cells pass; all six must). "
            f"Hypotheses tested so far: {HYPOTHESES_TESTED}.")
    add_evidence(conn, 32, "note", note, STATUS_VERDICT[status])
    set_status(conn, 32, status)
    return status, rows, note


def main():
    symbols = set(TREASURIES) | {"BIL", "VTI", "IEI", "VGIT", "VEA"}
    bars_all = {s: load_bars(s) for s in sorted(symbols)}
    conn = connect()
    summary = {}
    for hid, scorer in ((31, score_h31), (32, score_h32)):
        status, rows, note = scorer(conn, bars_all)
        summary[hid] = {"status": status, "note": note, "cells": rows}
        print(f"H{hid}: {status} - {note}")
        for row in rows:
            key = row.get("symbol") or row.get("universe")
            extra = (f"placebo {row['placebo']:.2f} rped {row['strategy']['return_per_exposure_day']:.3%}/"
                     f"{row['buy_and_hold']['mean_daily_return']:.3%}" if hid == 31 else
                     f"active {row['net_active']:.2%}/yr placebos {row['placebo_shift']:.2f}/{row['placebo_shuffle']:.2f}")
            print(f"  {key:9s} {row['window']:3s} events {row['events']:3d} mean {row['mean_event']:.3%} "
                  f"late {row['mean_event_delayed']:.3%} hit {row['hit_rate']:.0%} {extra} -> {row['verdict']}: {row['why']}")
    conn.close()
    out = ROOT / "backtests" / "round4_summary.json"
    out.write_text(json.dumps(summary, indent=2) + "\n")
    print(f"wrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
