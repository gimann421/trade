"""Exception hierarchy. Every failure mode that must fail closed has its own type."""


class NexusError(Exception):
    """Base class for all NEXUS errors."""


class LaunchBoundaryViolation(NexusError):
    """An action outside the Stage 0 authority boundary was attempted."""


class GovernanceError(NexusError):
    """Constitution, risk limits, permissions or promotion criteria changed or invalid."""


class ConfigError(NexusError):
    """Configuration is missing, malformed or contains a forbidden value."""


class SecretError(NexusError):
    """A secret is missing, or a secret was found where none may appear."""


class ImmutabilityError(NexusError):
    """An append-only record was modified or deleted."""


class AuditChainError(NexusError):
    """The audit hash chain does not verify."""


class StaleOrInvalidDataError(NexusError):
    """Critical input is stale, missing or contradictory (fail closed)."""


class SystemHalted(NexusError):
    """The emergency stop or a pause is active; new simulated orders are blocked."""
