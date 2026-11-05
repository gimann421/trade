"""Typed, validated, immutable domain models."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ..errors import NexusError, StaleOrInvalidDataError
from ..timeutil import require_aware, to_iso
from .enums import AssetClass, CapabilityTier, DataQuality, LedgerKind

__all__ = ["Instrument", "DataSnapshot", "LedgerAccount", "canonical_json", "content_hash"]


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def content_hash(obj: Any) -> str:
    return hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Instrument:
    """Spec 2.3 (subset for Milestone 1; contract/roll/margin details arrive in Milestone 2)."""
    instrument_id: str                      # canonical, e.g. "EQ:XNAS:AAPL"
    symbols: dict[str, str]                 # vendor/venue -> symbol
    asset_class: AssetClass
    currency: str
    timezone: str
    exchange: str | None = None
    capability_tier: CapabilityTier = CapabilityTier.R0
    contract_multiplier: float = 1.0
    tick_size: float | None = None
    jurisdiction: str | None = None
    known_failure_modes: tuple[str, ...] = ()

    def __post_init__(self):
        if not self.instrument_id or ":" not in self.instrument_id:
            raise NexusError("instrument_id must look like 'CLASS:VENUE:SYMBOL'")
        if not self.symbols:
            raise NexusError("instrument needs at least one symbol mapping")
        if len(self.currency) != 3 or not self.currency.isalpha() or not self.currency.isupper():
            raise NexusError("currency must be a 3-letter upper-case ISO code")
        try:
            ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise NexusError(f"unknown timezone {self.timezone!r}") from exc
        if self.contract_multiplier <= 0:
            raise NexusError("contract_multiplier must be positive")
        if self.tick_size is not None and self.tick_size <= 0:
            raise NexusError("tick_size must be positive")

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["asset_class"] = self.asset_class.value
        d["capability_tier"] = self.capability_tier.value
        d["known_failure_modes"] = list(self.known_failure_modes)
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Instrument":
        d = dict(d)
        d["asset_class"] = AssetClass(d["asset_class"])
        d["capability_tier"] = CapabilityTier(d["capability_tier"])
        d["known_failure_modes"] = tuple(d.get("known_failure_modes", ()))
        return cls(**d)


@dataclass(frozen=True)
class DataSnapshot:
    """Lineage record for a batch of data: where it came from and when it was valid/ingested."""
    snapshot_id: str
    source: str                  # vendor / adapter name
    as_of: datetime              # time the data describes (tz-aware)
    ingested_at: datetime        # when we received it (tz-aware)
    content_sha256: str
    quality: DataQuality = DataQuality.UNVERIFIED
    license_note: str | None = None

    def __post_init__(self):
        require_aware(self.as_of, "as_of")
        require_aware(self.ingested_at, "ingested_at")
        if not self.source:
            raise NexusError("data snapshot requires a source")
        if self.as_of > self.ingested_at:
            raise StaleOrInvalidDataError("data claims to be as-of a time after it was ingested")

    def age_seconds(self, now: datetime) -> float:
        return (require_aware(now, "now") - self.as_of).total_seconds()

    def assert_fresh(self, now: datetime, max_age_seconds: float | None) -> None:
        """Fail closed: unknown staleness limit, bad quality or old data all raise."""
        if max_age_seconds is None:
            raise StaleOrInvalidDataError("no staleness limit configured; cannot treat data as current")
        if self.quality is not DataQuality.OK:
            raise StaleOrInvalidDataError(f"snapshot {self.snapshot_id} quality is {self.quality.value}")
        if self.age_seconds(now) > max_age_seconds:
            raise StaleOrInvalidDataError(f"snapshot {self.snapshot_id} is stale")

    def to_dict(self) -> dict[str, Any]:
        return {"snapshot_id": self.snapshot_id, "source": self.source, "as_of": to_iso(self.as_of),
                "ingested_at": to_iso(self.ingested_at), "content_sha256": self.content_sha256,
                "quality": self.quality.value, "license_note": self.license_note}


@dataclass(frozen=True)
class LedgerAccount:
    account_id: str
    kind: LedgerKind
    name: str
    created_at: datetime = field(compare=False)
