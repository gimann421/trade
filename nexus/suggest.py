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
    resolved = [k for k in prev if k not in current]
    return lines, resolved, update


def run(snapshot: dict, adapter: MarketDataAdapter, now: datetime, state: dict, *, themes: dict[str, str] | None = None,
        fallback: dict[str, Decimal] | None = None) -> dict:
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
