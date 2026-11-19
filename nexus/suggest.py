"""Proactive, advisory suggestions for the owner's real portfolio (read-only; the owner acts himself).

Stateless apart from a private state file kept OUTSIDE git. Each run: price the held snapshot from the latest daily
closes (labelled fallback marks only where the feed has none), run the deterministic ``analyze`` checks, compare with
the last *posted* state, and report only what is new or materially changed. Nothing here can place an order or touch
the real account.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Callable

from .adapters.base import MarketDataAdapter
from .errors import NexusError
from .ideas import UNIVERSE, current_ideas, iid
from .recommendations import Finding, analyze
from .calendars import NY
from .timeutil import require_aware, to_iso

BROAD = frozenset({"VTI", "VXUS", "RSP"})
WEIGHT_STEP = Decimal("0.015")     # a weight finding is re-reported when it moves by this much
LOSS_STEP = Decimal("500")         # ... and an unrealized loss when it moves by this many dollars
CASH_STEP = Decimal("0.01")
STALE_BAR_DAYS = 5                 # a close older than this is not used; a labelled fallback mark is, or the run fails


def price_snapshot(snapshot: dict, adapter: MarketDataAdapter, now: datetime,
                   fallback: dict[str, Decimal]) -> tuple[dict[str, Decimal], dict[str, str]]:
    fallback = {**fallback, **{k.rsplit(":", 1)[-1]: v for k, v in fallback.items()}}   # accept bare or full ids
    prices: dict[str, Decimal] = {}
    notes: dict[str, str] = {}
    today = now.astimezone(NY).date()
    for iid in snapshot["holdings"]:
        got = None
        try:
            bars = adapter.fetch_daily_bars(iid, today - timedelta(days=14), today).bars
            bars = [b for b in bars if date.fromisoformat(b.session_date) <= today]
            if bars:
                last = max(bars, key=lambda b: b.session_date)
                if (today - date.fromisoformat(last.session_date)).days <= STALE_BAR_DAYS and last.close > 0:
                    got = (Decimal(str(last.close)), last.session_date)
        except Exception:
            got = None
        if got:
            prices[iid] = got[0]
        elif iid in fallback:
            prices[iid] = fallback[iid]
            notes[iid] = "no fresh feed price; using the last screenshot mark"
        else:
            raise NexusError(f"no price for {iid}: refusing to give suggestions on partial data")
    return prices, notes


def _key(f: Finding) -> str:
    return f"{f.kind}:{f.subject}"


def _magnitude(f: Finding) -> Decimal:
    ev = f.evidence
    if "weight" in ev:
        return Decimal(ev["weight"])
    if "unrealized" in ev:
        return Decimal(ev["unrealized"])
    return Decimal(0)


def _step(f: Finding) -> Decimal:
    return LOSS_STEP if f.kind == "tax_loss_candidate" else (CASH_STEP if f.kind == "cash_share" else WEIGHT_STEP)


def diff_findings(findings: list[Finding], prev: dict[str, dict], remind_cash: bool) -> tuple[list[str], list[str], set[str]]:
    """Return (lines, resolved keys, keys whose posted magnitude should be updated). ``prev``: key -> {"mag": str}."""
    lines, current, update = [], set(), set()
    for f in findings:
        k = _key(f)
        current.add(k)
        old = prev.get(k)
        mag = _magnitude(f)
        if old is None:
            lines.append(f"NEW - {f.summary}")
            update.add(k)
        elif abs(mag - Decimal(old["mag"])) >= _step(f):
            lines.append(f"CHANGED - {f.summary}")
            update.add(k)
        elif f.kind == "cash_share" and remind_cash:
            lines.append(f"STILL OPEN - {f.summary}")
    resolved = [k for k in prev if k not in current and not k.startswith(("buy_idea:", "buy_call:", "sell_call:"))]
    return lines, resolved, update


def fetch_universe(adapter: MarketDataAdapter, now: datetime) -> dict:
    """Daily history for the research universe; an instrument with a fetch problem is simply left out (ideas, not risk checks)."""
    today = now.astimezone(NY).date()
    out = {}
    for s in UNIVERSE:
        try:
            bars = adapter.fetch_daily_bars(iid(s), today - timedelta(days=520), today).bars
            if bars and (today - date.fromisoformat(max(b.session_date for b in bars))).days <= STALE_BAR_DAYS:
                out[iid(s)] = sorted(bars, key=lambda b: b.session_date)
        except Exception:
            continue
    return out


EVIDENCE = ("Evidence: strategy G1 (trend-following momentum) backtested at about 13%/yr net on 2021-24 and 50%/yr on 2024-25 versus "
            "3% and 22% for SPY, but it narrowly missed our own pass bar and has not been independently validated or forward-tested "
            "(forward test began 2026-11-19). Treat as a reasoned, unproven call.")
STOP_PCT = Decimal("0.12")
SELL_MOMENTUM = -0.35


def fetch_symbols(adapter: MarketDataAdapter, now: datetime, symbols) -> dict:
    today = now.astimezone(NY).date()
    out = {}
    for s in symbols:
        try:
            bars = adapter.fetch_daily_bars(iid(s), today - timedelta(days=520), today).bars
            if bars:
                out[s] = sorted(bars, key=lambda b: b.session_date)
        except Exception:
            continue
    return out


def call_lines(snapshot: dict, prices: dict[str, Decimal], hist: dict, held_hist: dict, prev: dict[str, dict], now: datetime) -> tuple[list[str], dict]:
    """Firm, actionable calls for the owner's own trades: ticker, shares, limit, reason, stop, and how well tested it is."""
    from .ideas import momentum, trend_ok
    cash = sum((Decimal(v) for v in snapshot["cash"].values()), Decimal(0))
    nav = cash + sum((Decimal(h["quantity"]) * prices[i] for i, h in snapshot["holdings"].items()), Decimal(0))
    held = {i.rsplit(":", 1)[-1] for i in snapshot["holdings"]}
    lines, keep, spend = [], {}, Decimal(0)
    for idea in current_ideas(hist, held):
        sym = idea.instrument_id.rsplit(":", 1)[-1]
        k = f"buy_call:{sym}"
        last = Decimal(str(hist[idea.instrument_id][-1].close))
        limit = (last * Decimal("1.003")).quantize(Decimal("0.01"))
        amt = Decimal(str(idea.suggested_weight)) * nav
        shares = int(amt // limit)
        if shares < 1 or spend + shares * limit > cash:
            continue
        spend += shares * limit
        keep[k] = {"mag": str(idea.suggested_weight), "at": to_iso(now)}
        if k not in prev:
            lines.append(f"BUY {sym}: {shares} shares, limit ${limit} (about ${shares * limit:,.0f}, paid from your cash). "
                         f"Why: {sym} is up {idea.momentum:+.0%} over ~6 months and trading above its 200-day average. "
                         f"Exit: sell if it closes below ${(limit * (1 - STOP_PCT)).quantize(Decimal('0.01'))} ({STOP_PCT:.0%} stop), "
                         f"or at month-end if it is no longer a top trend name. {EVIDENCE}")
    for iid_, h in snapshot["holdings"].items():
        sym = iid_.rsplit(":", 1)[-1]
        bs = held_hist.get(sym)
        if not bs or h.get("cost_basis") is None or sym in BROAD:
            continue
        m = momentum(bs)
        px = prices[iid_]
        loss = Decimal(h["quantity"]) * px - Decimal(h["cost_basis"])
        if m is not None and m <= SELL_MOMENTUM and not trend_ok(bs) and loss <= -LOSS_STEP:
            k = f"sell_call:{sym}"
            keep[k] = {"mag": str(loss.quantize(Decimal('1'))), "at": to_iso(now)}
            if k not in prev:
                limit = (px * Decimal("0.997")).quantize(Decimal("0.01"))
                lines.append(f"SELL {sym}: all {h['quantity']} shares, limit ${limit} (about ${Decimal(h['quantity']) * limit:,.0f}). "
                             f"Why: down {abs(m):.0%} over ~6 months, below its 200-day average, and already ${-loss:,.0f} under your cost basis, "
                             "so selling also books a loss you can use against gains if this is a taxable account. "
                             "Do not buy it back within 30 days (wash-sale rule, including your other accounts); check lot dates. "
                             "Not selling means accepting that the downtrend may reverse. " + EVIDENCE)
    return lines, keep


def run(snapshot: dict, adapter: MarketDataAdapter, now: datetime, state: dict, *, themes: dict[str, str] | None = None,
        fallback: dict[str, Decimal] | None = None, ideas: bool = True) -> dict:
    """Pure with respect to disk: returns {"post", "lines", "state", "log"}; the caller persists ``state``."""
    require_aware(now, "now")
    prices, notes = price_snapshot(snapshot, adapter, now, fallback or {})
    findings = analyze(snapshot, prices, now, themes=themes, broad_funds=BROAD)
    prev = state.get("posted", {})
    weekday = now.astimezone(NY).weekday()
    remind_cash = weekday == 0                      # the open cash question is repeated every Monday until answered
    lines, resolved, update = diff_findings(findings, prev, remind_cash)
    if resolved:
        lines += [f"RESOLVED - {k} no longer applies" for k in resolved]
    new_state = dict(state)
    posted = {k: v for k, v in prev.items() if k not in resolved}
    for f in findings:
        if _key(f) in update:
            posted[_key(f)] = {"mag": str(_magnitude(f)), "at": to_iso(now)}
    if ideas:
        try:
            held_syms = [i.rsplit(":", 1)[-1] for i in snapshot["holdings"]]
            pc = {k: v for k, v in posted.items() if k.startswith(("buy_call:", "sell_call:"))}
            il, keep = call_lines(snapshot, prices, fetch_universe(adapter, now), fetch_symbols(adapter, now, held_syms), pc, now)
            lines += il
            posted = {k: v for k, v in posted.items() if not k.startswith(("buy_call:", "sell_call:", "buy_idea:"))}
            posted.update(keep)
        except Exception:
            pass                                    # ideas are optional; the risk checks above never depend on them
    new_state["posted"] = posted
    new_state["last_run"] = to_iso(now)
    return {"post": bool(lines), "lines": lines, "state": new_state, "price_notes": notes,
            "log": {"at": to_iso(now), "findings": len(findings), "reported": len(lines)}}


def run_files(snapshot_path: str, state_path: str, adapter_factory: Callable[[], MarketDataAdapter], now: datetime,
              themes_path: str | None = None, fallback_path: str | None = None) -> dict:
    snap = json.loads(Path(snapshot_path).read_text())
    themes = json.loads(Path(themes_path).read_text()) if themes_path else None
    fb = {k: Decimal(str(v)) for k, v in json.loads(Path(fallback_path).read_text()).items()} if fallback_path else {}
    sp = Path(state_path)
    state = json.loads(sp.read_text()) if sp.exists() else {}
    res = run(snap, adapter_factory(), now, state, themes=themes, fallback=fb)
    sp.parent.mkdir(parents=True, exist_ok=True)
    sp.write_text(json.dumps(res["state"], indent=2, sort_keys=True))
    with open(sp.with_suffix(".log.jsonl"), "a") as fh:
        fh.write(json.dumps(res["log"]) + "\n")
    return {k: res[k] for k in ("post", "lines", "price_notes")}
