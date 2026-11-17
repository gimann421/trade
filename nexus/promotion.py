"""Independent strategy-promotion workflow (spec 4.7, 4.8, 7.4). Tiers Q0..Q7, no skipping, no self-certification.

Evidence is recomputed here from stored, hash-verified experiments; a reviewer cannot pass a hypothesis whose
pre-registered criteria fail. Q7 only means "eligible for human consideration": it grants no capability.
"""
from __future__ import annotations

import json
from datetime import datetime

from . import permissions
from .domain.enums import CapabilityTier, EventType, PromotionTier
from .errors import NexusError
from .research import evaluate_criteria, get_hypothesis
from .store import Store
from .timeutil import require_aware, to_iso

TIERS = [t.value for t in PromotionTier]
RED_TEAM, COMMITTEE, QUANT = "red_team", "validation_committee", "quant_lab"
ROLES = {RED_TEAM, COMMITTEE, QUANT, "owner"}


def current_tier(store: Store, hyp_id: str, version: int) -> str:
    get_hypothesis(store, hyp_id, version)
    r = store.conn.execute("SELECT to_tier FROM promotion_decisions WHERE hyp_id=? AND version=? AND "
                           "(decision='pass' OR reasons LIKE 'DEMOTION%') ORDER BY seq DESC LIMIT 1", (hyp_id, version)).fetchone()
    return r["to_tier"] if r else "Q0"


def _exp(store, hyp_id, version, segment):
    r = store.conn.execute("SELECT * FROM experiments WHERE hyp_id=? AND version=? AND segment=? ORDER BY created_at DESC LIMIT 1",
                           (hyp_id, version, segment)).fetchone()
    return None if r is None else (json.loads(r["result_json"]), r["code_commit"])


def _passed_by(store, hyp_id, version, tier, role):
    return store.conn.execute("SELECT 1 FROM promotion_decisions WHERE hyp_id=? AND version=? AND to_tier=? AND decision='pass' AND role=?",
                              (hyp_id, version, tier, role)).fetchone() is not None


def decide(store: Store, hyp_id: str, version: int, to_tier: str, decision: str, decided_by: str, role: str, reasons: str,
           now: datetime, evidence: dict | None = None) -> str:
    """Record a promotion decision. Raises if the rules are not met; returns the tier after the decision."""
    h = get_hypothesis(store, hyp_id, version)
    evidence = evidence or {}
    if to_tier not in TIERS or decision not in ("pass", "fail", "defer") or role not in ROLES:
        raise NexusError("bad tier, decision or role")
    if not reasons.strip():
        raise NexusError("reasons are required")
    cur = current_tier(store, hyp_id, version)
    if decision == "pass":
        if TIERS.index(to_tier) != TIERS.index(cur) + 1:
            raise NexusError(f"promotion must go {cur} -> {TIERS[min(TIERS.index(cur) + 1, 7)]}; tiers cannot be skipped")
        req = store.config.promotion["tiers"][to_tier]["requires_independent_review"]
        if store.config.promotion["rules"]["self_promotion_allowed"] is not False or decided_by == h["author"]:
            raise NexusError("the strategy author cannot certify or promote their own strategy")
        if req and role not in (RED_TEAM, COMMITTEE):
            raise NexusError(f"{to_tier} requires an independent {RED_TEAM} or {COMMITTEE} decision")
        _check_evidence(store, h, hyp_id, version, to_tier, role, evidence)
    elif decision == "fail" and reasons.startswith("DEMOTION"):
        raise NexusError("use demote() for demotions")
    ev = store.events.append(EventType.PROMOTION_DECIDED, "promotion", decided_by,
                             {"hyp_id": hyp_id, "version": version, "from": cur, "to": to_tier, "decision": decision, "role": role})
    store.conn.execute("INSERT INTO promotion_decisions (hyp_id, version, from_tier, to_tier, decision, decided_at, decided_by, role, reasons, evidence_json)"
                       " VALUES (?,?,?,?,?,?,?,?,?,?)",
                       (hyp_id, version, cur, to_tier, decision, to_iso(require_aware(now)), decided_by, role, reasons,
                        json.dumps(evidence, sort_keys=True)))
    return current_tier(store, hyp_id, version)


def demote(store: Store, hyp_id: str, version: int, to_tier: str, decided_by: str, role: str, reasons: str, now: datetime) -> str:
    """Anyone with a recognised role may demote (the safe direction)."""
    cur = current_tier(store, hyp_id, version)
    if to_tier not in TIERS or TIERS.index(to_tier) >= TIERS.index(cur) or role not in ROLES:
        raise NexusError("a demotion must go to a lower tier")
    store.events.append(EventType.PROMOTION_DECIDED, "promotion", decided_by,
                        {"hyp_id": hyp_id, "version": version, "from": cur, "to": to_tier, "decision": "demotion", "role": role})
    store.conn.execute("INSERT INTO promotion_decisions (hyp_id, version, from_tier, to_tier, decision, decided_at, decided_by, role, reasons, evidence_json)"
                       " VALUES (?,?,?,?,?,?,?,?,?,?)",
                       (hyp_id, version, cur, to_tier, "fail", to_iso(require_aware(now)), decided_by, role, "DEMOTION: " + reasons, "{}"))
    return to_tier


def _check_evidence(store, h, hyp_id, version, to_tier, role, evidence):
    crit = h["success_criteria"]
    if to_tier == "Q2":
        if _exp(store, hyp_id, version, "train") is None:
            raise NexusError("Q2 needs a recorded train experiment")
    elif to_tier == "Q3":
        if _exp(store, hyp_id, version, "train") is None or role != RED_TEAM:
            raise NexusError("Q3 needs a train experiment and a Red Team pass")
        if not evidence.get("flaws_addressed_or_disclosed"):
            raise NexusError("Q3 evidence must list flaws addressed or disclosed")
    elif to_tier == "Q4":
        if role != COMMITTEE:
            raise NexusError("Q4 is decided by the validation committee")
        for seg in ("validation", "holdout"):
            e = _exp(store, hyp_id, version, seg)
            if e is None:
                raise NexusError(f"Q4 needs a recorded {seg} experiment")
            result, commit = e
            if commit == "unknown" or commit.endswith("+dirty"):
                raise NexusError(f"{seg} experiment is not reproducible from a clean code commit ({commit})")
            fails = evaluate_criteria(crit, result)
            if fails:
                raise NexusError(f"pre-registered criteria failed on {seg}: {'; '.join(fails)}")
        if not _passed_by(store, hyp_id, version, "Q3", RED_TEAM):
            raise NexusError("Q4 requires a prior Red Team pass at Q3")
    elif to_tier == "Q5":
        if role != COMMITTEE or not (evidence.get("execution_model_reviewed") and evidence.get("monitoring_ready")):
            raise NexusError("Q5 needs the committee to confirm execution model review and monitoring")
        plan = h.get("paper_plan") or {}
        if not (plan.get("min_days") and plan.get("min_fills")):
            raise NexusError("Q5 requires a paper_plan (min_days, min_fills) pre-registered in the hypothesis")
        for iid in h["asset_universe"]:
            inst = store.get_instrument(iid)
            if inst is None or inst.capability_tier.rank < CapabilityTier.R2.rank:
                raise NexusError(f"{iid} is not paper-eligible (needs tier R2+)")
    elif to_tier == "Q6":
        plan = h.get("paper_plan") or {}
        if role != COMMITTEE or not plan:
            raise NexusError("Q6 is decided by the committee against the pre-registered paper_plan")
        if evidence.get("paper_days", 0) < plan["min_days"] or evidence.get("paper_fills", 0) < plan["min_fills"]:
            raise NexusError("paper observations are below the pre-registered minimums")
    elif to_tier == "Q7":
        if role != COMMITTEE:
            raise NexusError("Q7 is decided by the committee")
        permissions.require(permissions.Capability.RESEARCH)  # Q7 only marks eligibility for human review; grants nothing
