"""Score hypotheses 2-13 against the kill thresholds fixed in their 2026-10-12 memos.

    PYTHONPATH=. python research/round1_verdicts.py

For each hypothesis and each cell (SPY/QQQ x in-sample/out-of-sample) this runs the
backtest on full-history signals scored on the window, saves it under backtests/, and logs
one evidence row. The hypothesis is then marked:
  rejected  - any cell fails its kill threshold
  testing   - no cell fails but at least one is inconclusive (too few trades)
  supported - all four cells pass
The rules below are transcribed from the memos; they were not changed after seeing results.
"""

from core.backtest import load_strategy, run_backtest, save_result
from core.config import ROOT
from core.data import load_bars
from core.ledger import add_evidence, connect, set_status, set_strategy

SYMBOLS = ("SPY", "QQQ")
WINDOWS = {"IS": ("2016-01-01", "2022-12-31"), "OOS": ("2023-01-01", None)}


def drawdown_rule(r):
    """Trend and volatility memos: Sharpe >= buy-and-hold and max drawdown >= 5 points shallower."""
    s, b = r["strategy"], r["buy_and_hold"]
    fails = []
    if s["sharpe"] < b["sharpe"]:
        fails.append(f"Sharpe {s['sharpe']:.2f} < buy&hold {b['sharpe']:.2f}")
    if s["max_drawdown"] - b["max_drawdown"] < 0.05:
        fails.append(f"MaxDD {s['max_drawdown']:.1%} not 5pts better than {b['max_drawdown']:.1%}")
    return fails


def per_day_rule(mult, sharpe_frac=1.0):
    """Mean-reversion and calendar memos: return per exposure day and a Sharpe floor."""
    def rule(r):
        s, b = r["strategy"], r["buy_and_hold"]
        fails = []
        if s["sharpe"] < sharpe_frac * b["sharpe"]:
            fails.append(f"Sharpe {s['sharpe']:.2f} < {sharpe_frac:g}x buy&hold {b['sharpe']:.2f}")
        if s["return_per_exposure_day"] < mult * b["mean_daily_return"]:
            fails.append(f"return/exposure day {s['return_per_exposure_day']:.3%} < "
                         f"{mult:g}x buy&hold {b['mean_daily_return']:.3%}")
        return fails
    return rule


HYPOTHESES = {
    # id: (strategy file, kill rule, inconclusive test)
    2: ("vol_target_v1.py", drawdown_rule, None),
    3: ("tsmom_ladder_v1.py", drawdown_rule, None),
    4: ("donchian_breakout_v1.py", drawdown_rule, None),
    5: ("rsi2_pullback_v1.py", per_day_rule(2), ("entries", 15)),
    6: ("down_streak_v1.py", per_day_rule(2), ("entries", 15)),
    7: ("ibs_reversal_v1.py", per_day_rule(2), ("entries", 15)),
    8: ("vol_ratio_switch_v1.py", drawdown_rule, ("exits", 2)),
    9: ("gap_cluster_exit_v1.py", drawdown_rule, ("exits", 2)),
    10: ("range_shock_timeout_v1.py", drawdown_rule, ("exits", 2)),
    11: ("turn_of_month_v1.py", per_day_rule(2), ("entries", 20)),
    12: ("pre_holiday_v1.py", per_day_rule(3, sharpe_frac=0.5), ("entries", 20)),
    13: ("opex_week_v1.py", per_day_rule(2), ("entries", 20)),
}


def score(hypothesis_id, conn, bars):
    filename, rule, minimum = HYPOTHESES[hypothesis_id]
    strategy = load_strategy(ROOT / "strategies" / filename)
    set_strategy(conn, hypothesis_id, filename)
    set_status(conn, hypothesis_id, "testing")
    cells = []
    for symbol in SYMBOLS:
        for label, (start, end) in WINDOWS.items():
            result = run_backtest(bars[symbol], strategy.generate_signals, 5.0, start, end)
            path = save_result(result, strategy, symbol, window=f"{result['start']}_{result['end']}")
            s, b = result["strategy"], result["buy_and_hold"]
            fails = rule(result)
            too_few = minimum is not None and s[minimum[0]] < minimum[1]
            verdict = "contradicts" if fails else "inconclusive" if too_few else "supports"
            why = "; ".join(fails) if fails else (f"only {s[minimum[0]]} {minimum[0]}" if too_few
                                                   else "passes kill threshold")
            summary = (f"{filename[:-3]} {symbol} {label} {result['start']}..{result['end']}, 5 bps: "
                       f"Sharpe {s['sharpe']:.2f} vs {b['sharpe']:.2f}, MaxDD {s['max_drawdown']:.1%} vs "
                       f"{b['max_drawdown']:.1%}, CAGR {s['cagr']:.1%} vs {b['cagr']:.1%}, exposure "
                       f"{s['exposure']:.0%}, {s['entries']} entries. {verdict}: {why}")
            add_evidence(conn, hypothesis_id, "backtest", summary, verdict,
                         ref=str(path.relative_to(ROOT)))
            cells.append({"symbol": symbol, "window": label, "result": result, "verdict": verdict,
                          "why": why, "ref": str(path.relative_to(ROOT))})
    verdicts = {c["verdict"] for c in cells}
    status = "rejected" if "contradicts" in verdicts else "testing" if "inconclusive" in verdicts else "supported"
    set_status(conn, hypothesis_id, status)
    passed = sum(c["verdict"] == "supports" for c in cells)
    add_evidence(conn, hypothesis_id, "note", f"Round-1 verdict: {status} ({passed}/4 cells pass the "
                 f"pre-set kill threshold).",
                 {"rejected": "contradicts", "testing": "inconclusive", "supported": "supports"}[status])
    return status, cells


def main():
    bars = {symbol: load_bars(symbol) for symbol in SYMBOLS}
    conn = connect()
    for hypothesis_id in HYPOTHESES:
        status, cells = score(hypothesis_id, conn, bars)
        print(f"H{hypothesis_id} {HYPOTHESES[hypothesis_id][0]}: {status}")
        for c in cells:
            s, b = c["result"]["strategy"], c["result"]["buy_and_hold"]
            print(f"  {c['symbol']} {c['window']:3s} Sharpe {s['sharpe']:.2f}/{b['sharpe']:.2f} "
                  f"MaxDD {s['max_drawdown']:.1%}/{b['max_drawdown']:.1%} "
                  f"ret/day {s['return_per_exposure_day']:.3%}/{b['mean_daily_return']:.3%} "
                  f"exp {s['exposure']:.0%} -> {c['verdict']} ({c['why']})")
    conn.close()


if __name__ == "__main__":
    main()
