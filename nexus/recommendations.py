"""Proactive, advisory recommendations on the owner's REAL portfolio (read-only; the owner acts, NEXUS never trades it).

Deterministic generators only (LLM agents arrive in Milestone 6 and must go through the same recording path).
Each recommendation is pre-registered (timestamped audit event) before any outcome, tied to the exact immutable
snapshot it was computed from, and is immutable; owner responses and outcomes are appended as notes.
Theme mappings and holdings stay in local, untracked files supplied by the caller, never in git.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from .accounting import ZERO, D, load_snapshot
from .domain.enums import EventType, LedgerKind
from .errors import NexusError, StaleOrInvalidDataError
from .store import Store
from .timeutil import from_iso, require_aware, to_iso

GENERATOR = "deterministic-v1"


@dataclass(frozen=True)
class Finding:
    kind: str
    subject: str
    severity: str
    summary: str
    evidence: dict


def analyze(snapshot: dict, prices: dict[str, Decimal], now: datetime, *, themes: dict[str, str] | None = None, broad_funds: frozenset[str] = frozenset(),
            single_flag: Decimal = Decimal("0.10"), theme_flag: Decimal = Decimal("0.20"),
            loss_flag_usd: Decimal = Decimal("500"), max_snapshot_age_days: int = 7) -> list[Finding]:
    """Pure function of (snapshot, prices, time). Fails closed if any held instrument lacks a price."""
    out: list[Finding] = []
    cash = sum((Decimal(v) for v in snapshot["cash"].values()), ZERO)
    vals = {}
    for iid, h in snapshot["holdings"].items():
        sym = iid.rsplit(":", 1)[-1]
        p = prices.get(iid) or prices.get(sym)
        if p is None or p <= 0:
            raise StaleOrInvalidDataError(f"no price for {iid}; cannot analyze")
        vals[iid] = (Decimal(h["quantity"]) * p, h)
    nav = cash + sum(v for v, _ in vals.values())
    if nav <= 0:
        raise StaleOrInvalidDataError("non-positive NAV")
    age = (require_aware(now, "now") - from_iso(snapshot["as_of"])).days
    if age > max_snapshot_age_days:
        out.append(Finding("stale_snapshot", "portfolio", "watch",
                           f"The holdings snapshot is {age} days old; refresh it before relying on any recommendation.",
                           {"age_days": age}))
    for iid, (v, h) in sorted(vals.items(), key=lambda t: -t[1][0]):
        w = v / nav
        if w > single_flag and iid.rsplit(':', 1)[-1] not in broad_funds:   # broad index funds are not single-name risk
            out.append(Finding("concentration_single", iid, "watch",
                               f"{iid.rsplit(':', 1)[-1]} is {w:.1%} of the portfolio (review threshold {single_flag:.0%}, a prompt to look, not a limit).",
                               {"weight": f"{w:.4f}", "value": str(v.quantize(Decimal('1')))}))
    if themes:
        tw: dict[str, Decimal] = {}
        for iid, (v, _) in vals.items():
            t = themes.get(iid.rsplit(":", 1)[-1])
            if t:
                tw[t] = tw.get(t, ZERO) + v
        for t, v in sorted(tw.items(), key=lambda x: -x[1]):
            if v / nav > theme_flag:
                out.append(Finding("concentration_theme", t, "watch",
                                   f"Holdings tagged '{t}' total {v / nav:.1%} of the portfolio (review threshold {theme_flag:.0%}). "
                                   "Funds like VTI also hold these names, so true exposure is higher.",
                                   {"weight": f"{v / nav:.4f}"}))
    for iid, (v, h) in sorted(vals.items()):
        if h.get("cost_basis") is None:
            continue
        loss = v - Decimal(h["cost_basis"])
        if loss <= -loss_flag_usd:
            out.append(Finding("tax_loss_candidate", iid, "info",
                               f"{iid.rsplit(':', 1)[-1]} is down about ${-loss:,.0f} versus cost basis. If this is a taxable account, "
                               "realizing losses can offset gains and up to $3,000 of ordinary income per year, with the rest carried forward. "
                               "Watch the 30-day wash-sale rule (it counts purchases in your other accounts) and check holding period and lot dates; "
                               "confirm with a tax professional.",
                               {"unrealized": str(loss.quantize(Decimal('1'))), "basis": h["cost_basis"],
                                "basis_is_estimated": "cost_basis" in " ".join(snapshot["estimated_fields"])}))
    cw = cash / nav
    out.append(Finding("cash_share", "cash", "info", f"Cash is {cw:.1%} of the portfolio. The owner said (2026-11-19) this is not deliberate, so NEXUS treats it as money to put to work once a call passes validation.",
                       {"weight": f"{cw:.4f}"}))
    return out


def record_findings(store: Store, account_id: str, snapshot_id: str, findings: list[Finding], now: datetime,
                    actor: str = "recommendations") -> list[str]:
    """Pre-register and persist findings. Idempotent per (snapshot, kind, subject). Returns the new rec ids."""
    kind = store.conn.execute("SELECT kind FROM ledger_accounts WHERE account_id=?", (account_id,)).fetchone()
    if kind is None or LedgerKind(kind["kind"]) is not LedgerKind.ACTUAL:
        raise NexusError("recommendations are about the ACTUAL portfolio account")
    load_snapshot(store, snapshot_id)  # verifies the hash
    new = []
    for f in findings:
        if store.conn.execute("SELECT 1 FROM recommendations WHERE snapshot_id=? AND kind=? AND subject=?",
                              (snapshot_id, f.kind, f.subject)).fetchone():
            continue
        ev = store.events.append(EventType.RECOMMENDATION_RECORDED, "recommendations", actor,
                                 {"kind": f.kind, "subject": f.subject, "severity": f.severity, "summary": f.summary,
                                  "snapshot_id": snapshot_id, "generator": GENERATOR}, occurred_at=now,
                                 idempotency_key=f"rec:{snapshot_id}:{f.kind}:{f.subject}")
        rid = f"rec-{uuid.uuid4().hex[:12]}"
        store.conn.execute("INSERT INTO recommendations VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                           (rid, to_iso(now), account_id, snapshot_id, f.kind, f.subject, f.severity, f.summary,
                            json.dumps(f.evidence, sort_keys=True), GENERATOR, ev.event_id))
        new.append(rid)
    return new


def add_note(store: Store, rec_id: str, author: str, kind: str, note: str, now: datetime) -> None:
    if not store.conn.execute("SELECT 1 FROM recommendations WHERE rec_id=?", (rec_id,)).fetchone():
        raise NexusError("unknown recommendation")
    store.conn.execute("INSERT INTO recommendation_notes (rec_id, at, author, kind, note) VALUES (?,?,?,?,?)",
                       (rec_id, to_iso(now), author, kind, note))
