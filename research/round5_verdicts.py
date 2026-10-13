"""Score hypothesis 33 against the rules fixed in research/r5-residual-momentum-2026-10-13.md.

    PYTHONPATH=. python research/round5_verdicts.py

Residual momentum on point-in-time S&P 500 members, top decile equal-weight, monthly, against an
equal-weight portfolio of all members. Windows: IS 2016-01-01..2022-12-31 (from the first holding
day), OOS 2023-01-01..end of data, 5 bps per unit of turnover. Needs data/sp500_members.csv and
data/sp500/ (python -m core.universe fetch / download) plus the factor ETFs in data/.
"""

import json

import numpy as np
import pandas as pd

from core.backtest import TRADING_DAYS, _metrics, save_result
from core.config import ROOT
from core.data import load_bars
from core.ledger import add_evidence, connect, set_status, set_strategy
from core.portfolio import load_portfolio_strategy, month_ends, simulate
from core.universe import (FIRST_MONTH_END, LAST_MONTH_END, MANIFEST_PATH, load_member_closes,
                           load_membership, month_end_members)

HID = 33
WINDOWS = {"IS": ("2016-01-01", "2022-12-31"), "OOS": ("2023-01-01", None)}
MIN_REBALANCES = {"IS": 48, "OOS": 36}
COST_BPS = 5.0
RULES = {"net_active": 0.02, "information_ratio": 0.3, "placebo": 0.95}
PLACEBO = {"n": 1000, "seed": 0}
STATUS_VERDICT = {"rejected": "contradicts", "testing": "inconclusive", "supported": "supports"}
HYPOTHESES_TESTED = 33


def load_inputs(module):
    membership = load_membership()
    wanted = sorted(month_end_members(membership, FIRST_MONTH_END, LAST_MONTH_END))
    index = load_bars("VTI").index
    close = load_member_closes(wanted).reindex(index)
    etf = pd.DataFrame({s: load_bars(s)["close"] for s in module.FACTOR_ETFS}).reindex(index)
    if etf.isna().any().any():
        raise ValueError("factor ETFs are missing bars on trading days")
    manifest = json.loads(MANIFEST_PATH.read_text())
    missing = sorted(set(wanted) - set(close.columns))
    return membership, close, module.factor_returns(etf), {"wanted": len(wanted), "with_bars": close.shape[1],
                                                           "missing": missing,
                                                           "missing_reasons": {t: manifest["missing"].get(t, "no file")
                                                                               for t in missing}}


def coverage(detail):
    share = [len(d["priced"]) / d["members"] for d in detail]
    ranked = [len(d["ranked"]) for d in detail]
    return {"rebalances": len(detail), "priced_share_min": float(min(share)), "priced_share_mean": float(np.mean(share)),
            "ranked_min": int(min(ranked)), "ranked_mean": float(np.mean(ranked)),
            "picks_mean": float(np.mean([len(d["picks"]) for d in detail]))}


def holding_windows(detail, index):
    """(decision date, first holding day, last holding day) per rebalance."""
    out = []
    for k, d in enumerate(detail):
        start = index[index.get_loc(d["date"]) + 1] if d["date"] != index[-1] else None
        end = detail[k + 1]["date"] if k + 1 < len(detail) else index[-1]
        if start is not None:
            out.append((d["date"], start, end))
    return out


def in_window(day, start, end):
    return day >= pd.Timestamp(start) and (end is None or day <= pd.Timestamp(end))


def selection_placebo(detail, close_ff, index, start, end):
    """Percentile of the strategy's mean monthly gross active return among random same-size baskets
    drawn from the same ranked names each month (benchmark = equal weight of priced members)."""
    rng = np.random.default_rng(PLACEBO["seed"])
    actual, draws = [], []
    for d, (date, first, last) in zip(detail, holding_windows(detail, index)):
        if not in_window(first, start, end):
            continue
        growth = close_ff.loc[last] / close_ff.loc[date] - 1
        bench = growth[d["priced"]].mean()
        ranked = growth[d["ranked"]].to_numpy()
        n = len(d["picks"])
        actual.append(growth[d["picks"]].mean() - bench)
        idx = np.argsort(rng.random((PLACEBO["n"], len(ranked))), axis=1)[:, :n]
        draws.append(ranked[idx].mean(axis=1) - bench)
    actual_mean = float(np.mean(actual))
    draw_means = np.mean(np.array(draws), axis=0)
    return actual_mean, float((draw_means < actual_mean).mean()), len(actual)


def window_stats(run, bench, first_hold, start, end):
    lo = max(pd.Timestamp(start), first_hold)
    s, b = run["returns"].loc[lo:end], bench["returns"].loc[lo:end]
    active = s - b
    years = len(s) / TRADING_DAYS
    return s, b, {
        "start": str(s.index[0].date()), "end": str(s.index[-1].date()), "days": len(s),
        "net_active": float(active.mean() * TRADING_DAYS),
        "information_ratio": float(active.mean() / active.std() * np.sqrt(TRADING_DAYS)),
        "tracking_error": float(active.std() * np.sqrt(TRADING_DAYS)),
        "beta_to_benchmark": float(np.cov(s, b)[0, 1] / b.var()),
        "annual_turnover": float(run["traded"].loc[lo:end].sum() / years),
        "benchmark_annual_turnover": float(bench["traded"].loc[lo:end].sum() / years),
        "strategy": _metrics(s), "benchmark": _metrics(b),
    }


def main():
    module = load_portfolio_strategy(ROOT / "strategies" / "residual_momentum_v1.py")
    membership, close, factors, cov_info = load_inputs(module)
    index = close.index
    decisions = index[month_ends(index)]
    close_ff = close.ffill()

    strat_t, bench_t, detail = module.generate_weights(close, factors, membership, decisions)
    plain_t, _, plain_detail = module.generate_weights(close, factors, membership, decisions,
                                                       score=module.total_return_scores)
    run = simulate(close_ff, strat_t, COST_BPS)
    bench = simulate(close_ff, bench_t, COST_BPS)
    late = simulate(close_ff, strat_t.shift(1), COST_BPS)
    late_bench = simulate(close_ff, bench_t.shift(1), COST_BPS)
    plain = simulate(close_ff, plain_t, COST_BPS)
    # spin-off check (reported only): single-day moves beyond -50% / +100% treated as data errors
    r = close_ff.pct_change(fill_method=None)
    r = r.mask((r < -0.5) | (r > 1.0), 0.0)
    clean_close = (1 + r.fillna(0.0)).cumprod().where(close_ff.notna())
    clean = simulate(clean_close, strat_t, COST_BPS)
    clean_bench = simulate(clean_close, bench_t, COST_BPS)
    first_hold = index[index.get_loc(detail[0]["date"]) + 1]
    cov = coverage(detail) | {"first_decision": str(detail[0]["date"].date()), "tickers_wanted": cov_info["wanted"],
                              "tickers_with_bars": cov_info["with_bars"], "missing": cov_info["missing_reasons"]}

    conn = connect()
    set_strategy(conn, HID, "residual_momentum_v1.py")
    set_status(conn, HID, "testing")
    cells, rows = {}, []
    windows = holding_windows(detail, index)
    for label, (start, end) in WINDOWS.items():
        s, b, stats = window_stats(run, bench, first_hold, start, end)
        _, _, late_stats = window_stats(late, late_bench, first_hold, start, end)
        _, _, plain_stats = window_stats(plain, bench, first_hold, start, end)
        _, _, clean_stats = window_stats(clean, clean_bench, first_hold, start, end)
        gross_active, pct, n_months = selection_placebo(detail, close_ff, index, start, end)
        rebalances = sum(in_window(first, start, end) for _, first, _ in windows)
        if rebalances < MIN_REBALANCES[label]:
            verdict, why = "inconclusive", f"only {rebalances} rebalances (need {MIN_REBALANCES[label]})"
        else:
            fails = []
            if stats["net_active"] < RULES["net_active"]:
                fails.append(f"net active {stats['net_active']:.2%}/yr < 2.0%")
            if stats["information_ratio"] < RULES["information_ratio"]:
                fails.append(f"information ratio {stats['information_ratio']:.2f} < 0.3")
            if pct < RULES["placebo"]:
                fails.append(f"placebo {pct:.3f} < 0.95")
            verdict, why = ("contradicts", "; ".join(fails)) if fails else ("supports", "passes kill rule")
        result = {"start": stats["start"], "end": stats["end"], "days": stats["days"], "cost_bps": COST_BPS,
                  "window": label, "rebalances": rebalances, "verdict": verdict, "why": why,
                  "placebo": {"gross_active_per_month": gross_active, "percentile": pct, "months": n_months,
                              "draws": PLACEBO["n"], "seed": PLACEBO["seed"]},
                  "stats": stats, "delayed_fill": {k: late_stats[k] for k in ("net_active", "information_ratio")},
                  "spin_off_check": {k: clean_stats[k] for k in ("net_active", "information_ratio")}
                  | {"strategy_cagr": clean_stats["strategy"]["cagr"], "benchmark_cagr": clean_stats["benchmark"]["cagr"]},
                  "plain_12_1_momentum": {k: plain_stats[k] for k in
                                          ("net_active", "information_ratio", "annual_turnover", "strategy")},
                  "coverage": cov, "equity_curve": (1 + s).cumprod()}
        path = save_result(result, module, "SP500PIT", window=f"{stats['start']}_{stats['end']}")
        summary = (f"residual_momentum_v1 top decile of PIT S&P 500 {label} {stats['start']}..{stats['end']}, 5 bps: "
                   f"{rebalances} rebalances, net active {stats['net_active']:.2%}/yr, IR {stats['information_ratio']:.2f}, "
                   f"placebo {pct:.3f} (gross active {gross_active:.2%}/month); CAGR {stats['strategy']['cagr']:.1%} vs "
                   f"EW members {stats['benchmark']['cagr']:.1%}, Sharpe {stats['strategy']['sharpe']:.2f} vs "
                   f"{stats['benchmark']['sharpe']:.2f}, beta {stats['beta_to_benchmark']:.2f}, turnover "
                   f"{stats['annual_turnover']:.1f}x/yr. Delayed fill net active {late_stats['net_active']:.2%}; plain "
                   f"12-1 momentum net active {plain_stats['net_active']:.2%}; spin-off check net active {clean_stats['net_active']:.2%} (not scored). {verdict}: {why}")
        add_evidence(conn, HID, "backtest", summary, verdict, ref=str(path.relative_to(ROOT)))
        cells[label] = verdict
        rows.append({k: v for k, v in result.items() if k not in ("equity_curve", "coverage")}
                    | {"ref": str(path.relative_to(ROOT))})
        print(summary)

    verdicts = set(cells.values())
    status = "supported" if verdicts == {"supports"} else "rejected" if "contradicts" in verdicts else "testing"
    note = (f"Round-5 verdict: {status} ({sum(v == 'supports' for v in cells.values())}/2 windows pass; both must). "
            f"Coverage: {cov['tickers_with_bars']}/{cov['tickers_wanted']} tickers with bars, priced members per "
            f"rebalance {cov['priced_share_min']:.1%} min / {cov['priced_share_mean']:.1%} mean. "
            f"Hypotheses tested so far: {HYPOTHESES_TESTED}.")
    add_evidence(conn, HID, "note", note, STATUS_VERDICT[status])
    set_status(conn, HID, status)
    conn.close()
    print(note)
    out = ROOT / "backtests" / "round5_summary.json"
    out.write_text(json.dumps({HID: {"status": status, "note": note, "coverage": cov, "cells": rows}},
                              indent=2, default=str) + "\n")
    print(f"wrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
