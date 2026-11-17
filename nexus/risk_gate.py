"""Deterministic pre-trade risk gate. No LLM path can override it: it has no inputs other than data."""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from .accounting import AccountState, ZERO
from .domain.enums import AssetClass, CapabilityTier, LedgerKind
from .domain.models import Instrument

TIER_RANK = {t.value: t.rank for t in CapabilityTier}


@dataclass
class RiskResult:
    approved: bool = True
    reasons: list[str] = field(default_factory=list)

    def reject(self, why: str) -> None:
        self.approved = False
        self.reasons.append(why)


def evaluate(limits: dict, account_kind: LedgerKind, inst: Instrument, side: str, qty: Decimal, price: Decimal,
             state: AccountState, marks: dict[str, Decimal]) -> RiskResult:
    r = RiskResult()
    if account_kind is LedgerKind.ACTUAL:
        r.reject("orders can never be placed against the ACTUAL ledger")
        return r
    d = limits.get("paper_sleeve_defaults") or {}
    launch = limits.get("launch_defaults") or {}
    need = d.get("min_instrument_tier_for_shadow" if account_kind is LedgerKind.SHADOW else "min_instrument_tier_for_paper")
    if need is None or "max_position_weight" not in d or d["max_position_weight"] is None:
        r.reject("risk limits not configured (fail closed)")
        return r
    if inst.capability_tier.rank < TIER_RANK[need]:
        r.reject(f"instrument tier {inst.capability_tier.value} below required {need}")
    if inst.asset_class is AssetClass.DERIVATIVE and not launch.get("allow_derivatives", False):
        r.reject("derivatives are not allowed at launch")
    if qty <= 0 or price <= 0:
        r.reject("quantity and price must be positive")
        return r
    held = state.positions.get(inst.instrument_id, ZERO)
    if side == "BUY":
        if qty * price > state.cash:
            r.reject("insufficient cash (no leverage at launch)")
    else:
        if qty > held:
            r.reject("sell exceeds position (shorting not allowed)")
    after = held + qty if side == "BUY" else held - qty
    marks = {**marks, inst.instrument_id: price}
    try:
        nav = state.cash + sum((q * marks[i] for i, q in state.positions.items()), ZERO)
    except KeyError:
        r.reject("a held instrument has no mark; NAV unpriceable")
        return r
    if nav <= 0:
        r.reject("non-positive NAV")
        return r
    if side == "BUY" and after * price / nav > Decimal(str(d["max_position_weight"])):
        r.reject(f"position would exceed max weight {d['max_position_weight']}")
    gross_after = sum((q * marks[i] for i, q in state.positions.items() if i != inst.instrument_id), ZERO) + after * price
    if gross_after / nav > Decimal(str(d.get("max_gross_leverage", launch.get("max_gross_leverage", 1)))):
        r.reject("gross leverage limit")
    return r
