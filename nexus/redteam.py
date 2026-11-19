"""Red Team (spec 4.7): deterministic attempts to falsify a strategy before anything is promoted or advised.

The engine is separate from the strategy author (role ``red_team``, identity ``redteam-engine``) and its incentives only
favour finding flaws: every check can fail the strategy, none can promote it. Findings are recorded as an immutable
promotion decision with the evidence. A human or independent reviewer still has to sign off on later tiers; this engine
can only block, never approve live-relevant status on its own.
"""
from __future__ import annotations

import random
from datetime import datetime

from .domain.models import Bar
from .errors import NexusError
from .ideas import buy_and_hold, iid
from .promotion import TIERS, current_tier, decide
from .research import BacktestConfig, evaluate_criteria, get_hypothesis, run_backtest
from .store import Store

ROLE, IDENTITY = "red_team", "redteam-engine"


def _meets(crit: dict, r: dict) -> bool:
    return not evaluate_criteria(crit, r)


def _random_strategy(universe: list[str], seed: int, n: int = 5):
    rng = random.Random(seed)
    cache: dict[str, dict[str, float]] = {}

    def strat(hist):
        dates = sorted({b.session_date for bs in hist.values() for b in bs})
        d = dates[-1]
        month = d[:7]
        if month not in cache:               # one random draw per month, held until the next month (no information used)
            pick = rng.sample([i for i in universe if i in hist], min(n, len([i for i in universe if i in hist])))
            cache[month] = {i: 0.99 / n for i in pick}
        return cache[month]
    return strat


def challenge(store: Store, hyp_id: str, version: int, bars: dict[str, list[Bar]], now: datetime, strategy, variants: list, trials: int = 30, quick: bool = True) -> dict:
    """``strategy`` is the registered rule; ``variants`` are nearby-setting versions of it (parameter-neighbour test)."""
    h = get_hypothesis(store, hyp_id, version)
    crit = h["success_criteria"]
    start, end = h["train_period"][0], h["validation_period"][1]
    cfg = BacktestConfig()
    findings: list[dict] = []

    def add(name: str, ok: bool, detail: str, hard: bool = True) -> None:
        findings.append({"check": name, "passed": bool(ok), "hard": hard, "detail": detail})

    # 1. pre-registered criteria on each recorded segment (re-evaluated from stored results, not from anyone's summary)
    import json
    for seg in ("train", "validation"):
        r = store.conn.execute("SELECT result_json FROM experiments WHERE hyp_id=? AND version=? AND segment=? ORDER BY created_at DESC LIMIT 1",
                               (hyp_id, version, seg)).fetchone()
        if r is None:
            add(f"criteria:{seg}", False, "no recorded experiment")
            continue
        fails = evaluate_criteria(crit, json.loads(r[0]))
        add(f"criteria:{seg}", not fails, "; ".join(fails) or "meets every pre-registered criterion")

    quick_fail = quick and any(not f["passed"] for f in findings)     # a strategy that already misses its own criteria needs no further proof
    if quick_fail:
        return _finish(store, hyp_id, version, findings, now)

    # 2. cost stress
    for seg in ("train", "validation"):
        a, b = h[f"{seg}_period"]
        res = run_backtest(bars, strategy, a, b, BacktestConfig(cost_multiplier=3.0))
        add(f"costs_x3:{seg}", res["cagr_net"] >= crit["min_cagr_net"], f"net CAGR {res['cagr_net']:.1%} at 3x costs (needs {crit['min_cagr_net']:.0%})")

    # 3. sub-period stability against SPY buy-and-hold, by calendar year inside train+validation
    spy_bars = {iid("SPY"): bars[iid("SPY")]} if iid("SPY") in bars else None
    years = sorted({d[:4] for bs in bars.values() for d in [b.session_date for b in bs] if start <= d < end})
    beat, tot = 0, 0
    for y in years:
        a, b = max(f"{y}-01-01", start), min(f"{int(y) + 1}-01-01", end)
        try:
            g = run_backtest(bars, strategy, a, b, cfg)["total_return"]
            s = run_backtest(spy_bars, buy_and_hold(iid("SPY")), a, b, cfg)["total_return"] if spy_bars else 0.0
        except Exception:
            continue
        tot += 1
        beat += g > s
    add("stability_vs_spy", tot > 0 and beat / tot >= 2 / 3, f"beat SPY in {beat} of {tot} calendar windows (needs two thirds)")

    # 4. parameter neighbours: a real edge should survive nearby settings
    ok_n = 0
    for v in variants:
        res = run_backtest(bars, v, start, end, cfg)
        ok_n += _meets(crit, res)
    add("parameter_neighbours", ok_n / len(variants) >= 0.6, f"{ok_n} of {len(variants)} nearby settings still meet the criteria (needs 60%)")

    # 5. luck: random monthly picks with no signal, same costs and window
    own = run_backtest(bars, strategy, start, end, cfg)["cagr_net"]
    universe = sorted(bars)
    rnd = sorted(run_backtest(bars, _random_strategy(universe, s), start, end, cfg)["cagr_net"] for s in range(trials))
    pct = sum(r < own for r in rnd) / trials
    add("beats_random_selection", pct >= 0.9, f"{hyp_id} {own:.1%} beat {pct:.0%} of {trials} signal-free random portfolios (needs 90%)")

    # 5b. multiple testing: the Sharpe must beat what the best of N zero-skill trials would reach by luck (Bailey and Lopez de Prado)
    from statistics import NormalDist
    n_trials = max(1, store.conn.execute("SELECT COUNT(*) FROM hypotheses").fetchone()[0])
    own_res = run_backtest(bars, strategy, start, end, cfg)
    yrs = max(own_res["observations"] / 252, 0.5)
    g, nd = 0.5772156649, NormalDist()
    sr0 = (1 / yrs ** 0.5) * ((1 - g) * nd.inv_cdf(1 - 1 / max(n_trials, 2)) + g * nd.inv_cdf(1 - 1 / (max(n_trials, 2) * 2.718281828)))
    add("deflated_sharpe", own_res["sharpe"] > sr0, f"Sharpe {own_res['sharpe']:.2f} vs {sr0:.2f} expected from the best of {n_trials} luck-only trials")

    # 6. disclosure items that cannot pass or fail mechanically
    n_hyp = store.conn.execute("SELECT COUNT(DISTINCT hyp_id) FROM hypotheses").fetchone()[0]
    add("multiple_testing", True, f"{n_hyp} distinct hypotheses registered so far; survivorship bias and a short sample are disclosed biases", hard=False)
    hold = store.conn.execute("SELECT 1 FROM experiments WHERE hyp_id=? AND version=? AND segment='holdout'", (hyp_id, version)).fetchone()
    add("holdout_sealed", hold is None, "holdout period has not been evaluated", hard=False)

    return _finish(store, hyp_id, version, findings, now)


def _finish(store: Store, hyp_id: str, version: int, findings: list[dict], now: datetime) -> dict:
    failed = [f for f in findings if f["hard"] and not f["passed"]]
    verdict = "fail" if failed else "defer"          # the engine can block; it never promotes
    cur = current_tier(store, hyp_id, version)
    nxt = TIERS[min(TIERS.index(cur) + 1, 7)]
    reasons = ("RED TEAM: " + ("; ".join(f"{f['check']}: {f['detail']}" for f in failed) if failed
                               else "no hard flaw found; independent human/committee review still required"))
    decide(store, hyp_id, version, nxt, verdict, IDENTITY, ROLE, reasons, now, {"findings": findings})
    return {"verdict": verdict, "tier": cur, "findings": findings}


def call_gate(store: Store, hyp_id: str, version: int) -> tuple[bool, list[str]]:
    """May strategy output be shown to the owner as an actionable call? Only when promoted to paper-eligible (Q5+), the
    owner's limits are set, and the audit chain verifies. Returns (ok, blocking reasons)."""
    why = []
    tier = current_tier(store, hyp_id, version)
    if TIERS.index(tier) < TIERS.index("Q5"):
        why.append(f"strategy is at {tier}; real-account calls need Q5 or higher (independent review and validation)")
    lim = store.config.risk_limits.get("owner_limits", {})
    if lim.get("max_position_weight") is None or lim.get("max_portfolio_drawdown") is None:
        why.append("owner limits are not set")
    try:
        store.events.verify_chain()
    except NexusError as exc:
        why.append(f"audit chain: {exc}")
    return (not why, why)
