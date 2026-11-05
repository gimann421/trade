"""The no-live-trading permission invariant.

The forbidden set below is hard-coded. Configuration may only *narrow* authority
(it can never add to it), and no code path, environment variable, agent or config
file can grant any capability in ``LAUNCH_FORBIDDEN`` while ``STAGE == 0``.

Stage advancement needs an explicit, documented owner authorization and a code
change reviewed by a human; it is deliberately not a runtime switch.
"""
from __future__ import annotations

from enum import Enum

from .errors import LaunchBoundaryViolation

STAGE = 0  # Stage 0 - build and verify (spec section 13)


class Capability(str, Enum):
    # Always-forbidden at launch
    BROKER_WRITE = "broker_write"
    SUBMIT_REAL_ORDER = "submit_real_order"
    MODIFY_REAL_ORDER = "modify_real_order"
    CANCEL_REAL_ORDER = "cancel_real_order"
    MOVE_MONEY = "move_money"
    WITHDRAW = "withdraw"
    TRANSFER = "transfer"
    ACCESS_PAYMENT_CREDENTIALS = "access_payment_credentials"
    GRANT_OWN_PERMISSIONS = "grant_own_permissions"
    EDIT_RISK_LIMITS = "edit_risk_limits"
    EDIT_PROMOTION_CRITERIA = "edit_promotion_criteria"
    LABEL_SIMULATED_AS_ACTUAL_FILL = "label_simulated_as_actual_fill"
    # Allowed at launch
    RESEARCH = "research"
    BACKTEST = "backtest"
    SIMULATE_ORDER = "simulate_order"
    RECORD_HYPOTHETICAL_TRADE = "record_hypothetical_trade"
    READ_ONLY_PORTFOLIO = "read_only_portfolio"


LAUNCH_FORBIDDEN: frozenset[Capability] = frozenset(
    {
        Capability.BROKER_WRITE,
        Capability.SUBMIT_REAL_ORDER,
        Capability.MODIFY_REAL_ORDER,
        Capability.CANCEL_REAL_ORDER,
        Capability.MOVE_MONEY,
        Capability.WITHDRAW,
        Capability.TRANSFER,
        Capability.ACCESS_PAYMENT_CREDENTIALS,
        Capability.GRANT_OWN_PERMISSIONS,
        Capability.EDIT_RISK_LIMITS,
        Capability.EDIT_PROMOTION_CRITERIA,
        Capability.LABEL_SIMULATED_AS_ACTUAL_FILL,
    }
)

LAUNCH_ALLOWED: frozenset[Capability] = frozenset(Capability) - LAUNCH_FORBIDDEN


def is_allowed(cap: Capability, narrowed_to: frozenset[Capability] | None = None) -> bool:
    """True only if ``cap`` is allowed at launch AND (if given) in the config's narrowing set."""
    if cap in LAUNCH_FORBIDDEN:
        return False
    if narrowed_to is not None and cap not in narrowed_to:
        return False
    return True


def require(cap: Capability, narrowed_to: frozenset[Capability] | None = None) -> None:
    """Raise ``LaunchBoundaryViolation`` unless ``cap`` is permitted. Fails closed."""
    if not isinstance(cap, Capability):
        raise LaunchBoundaryViolation(f"unknown capability {cap!r}; denied")
    if not is_allowed(cap, narrowed_to):
        raise LaunchBoundaryViolation(
            f"capability '{cap.value}' is not available at Stage {STAGE} (launch boundary)"
        )


def forbid_live(*_args, **_kwargs):
    """Placeholder for any future live pathway: always raises."""
    raise LaunchBoundaryViolation("live trading is technically unavailable at Stage 0")
