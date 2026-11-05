"""Controlled vocabularies from the master specification."""
from __future__ import annotations

from enum import Enum

__all__ = ["AssetClass", "CapabilityTier", "PromotionTier", "LedgerKind", "OrderState",
           "EventType", "DECISION_LIKE_EVENTS", "ALLOWED_ORDER_TRANSITIONS", "DataQuality"]


class AssetClass(str, Enum):
    EQUITY = "equity"
    FUND = "fund"
    FIXED_INCOME = "fixed_income"
    COMMODITY = "commodity"
    DERIVATIVE = "derivative"
    CURRENCY = "currency"
    DIGITAL_ASSET = "digital_asset"
    PREDICTION_MARKET = "prediction_market"
    OTHER = "other"


class CapabilityTier(str, Enum):
    """Spec 2.2. R4 is unavailable at launch."""
    R0 = "R0"  # discover only
    R1 = "R1"  # research and backtest
    R2 = "R2"  # paper eligible
    R3 = "R3"  # shadow eligible
    R4 = "R4"  # future live eligible (forbidden at launch)

    @property
    def rank(self) -> int:
        return int(self.value[1])


class PromotionTier(str, Enum):
    """Spec 7.4."""
    Q0 = "Q0"; Q1 = "Q1"; Q2 = "Q2"; Q3 = "Q3"
    Q4 = "Q4"; Q5 = "Q5"; Q6 = "Q6"; Q7 = "Q7"


class LedgerKind(str, Enum):
    """Spec 9.1: three separate ledgers. Never merged."""
    ACTUAL = "ACTUAL"
    SHADOW = "SHADOW"
    PAPER_SLEEVE = "PAPER_SLEEVE"


class DataQuality(str, Enum):
    OK = "ok"
    STALE = "stale"
    MISSING = "missing"
    CONFLICTING = "conflicting"
    UNVERIFIED = "unverified"


class OrderState(str, Enum):
    """Spec 8.3 paper ledger states."""
    PROPOSED = "PROPOSED"
    ACCEPTED_BY_SIMULATOR = "ACCEPTED_BY_SIMULATOR"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    OPEN = "OPEN"
    REDUCED = "REDUCED"
    CLOSED = "CLOSED"
    SETTLED = "SETTLED"
    REJECTED = "REJECTED"
    CANCELED = "CANCELED"
    EXPIRED = "EXPIRED"
    UNPRICEABLE = "UNPRICEABLE"
    DATA_INVALID = "DATA_INVALID"
    NEEDS_REVIEW = "NEEDS_REVIEW"


_S = OrderState
ALLOWED_ORDER_TRANSITIONS: dict[OrderState, frozenset[OrderState]] = {
    _S.PROPOSED: frozenset({_S.ACCEPTED_BY_SIMULATOR, _S.REJECTED, _S.UNPRICEABLE, _S.DATA_INVALID, _S.CANCELED, _S.EXPIRED, _S.NEEDS_REVIEW}),
    _S.ACCEPTED_BY_SIMULATOR: frozenset({_S.PARTIALLY_FILLED, _S.FILLED, _S.CANCELED, _S.EXPIRED, _S.REJECTED, _S.DATA_INVALID, _S.NEEDS_REVIEW}),
    _S.PARTIALLY_FILLED: frozenset({_S.PARTIALLY_FILLED, _S.FILLED, _S.CANCELED, _S.EXPIRED, _S.NEEDS_REVIEW}),
    _S.FILLED: frozenset({_S.OPEN, _S.NEEDS_REVIEW}),
    _S.OPEN: frozenset({_S.REDUCED, _S.CLOSED, _S.NEEDS_REVIEW}),
    _S.REDUCED: frozenset({_S.REDUCED, _S.CLOSED, _S.NEEDS_REVIEW}),
    _S.CLOSED: frozenset({_S.SETTLED, _S.NEEDS_REVIEW}),
    _S.SETTLED: frozenset(),
    _S.REJECTED: frozenset(),
    _S.CANCELED: frozenset(),
    _S.EXPIRED: frozenset(),
    _S.UNPRICEABLE: frozenset({_S.NEEDS_REVIEW}),
    _S.DATA_INVALID: frozenset({_S.NEEDS_REVIEW}),
    _S.NEEDS_REVIEW: frozenset({_S.PROPOSED, _S.REJECTED, _S.CANCELED}),
}


class EventType(str, Enum):
    SYSTEM_BOOT = "system.boot"
    GOVERNANCE_VERIFIED = "governance.verified"
    GOVERNANCE_LOCK_UPDATED = "governance.lock_updated"
    CONTROL_HALT = "control.halt"
    CONTROL_RESUME = "control.resume"
    INSTRUMENT_REGISTERED = "instrument.registered"
    LEDGER_ACCOUNT_CREATED = "ledger.account_created"
    DATA_SNAPSHOT_RECORDED = "data.snapshot_recorded"
    DATA_QUALITY_FAILED = "data.quality_failed"
    HYPOTHESIS_REGISTERED = "hypothesis.registered"
    DECISION_RECORDED = "decision.recorded"
    ORDER_STATE_CHANGED = "order.state_changed"
    CORRECTION = "record.correction"
    JOB_MISSED = "job.missed"


# Events that assert "this was decided at time T": must be stamped contemporaneously (no backdating).
DECISION_LIKE_EVENTS: frozenset[EventType] = frozenset(
    {EventType.DECISION_RECORDED, EventType.ORDER_STATE_CHANGED, EventType.HYPOTHESIS_REGISTERED}
)
