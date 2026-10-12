"""Load and validate config/risk_limits.yaml."""

from dataclasses import dataclass, fields
from pathlib import Path

import yaml

from core.config import ROOT, ConfigError

RISK_PATH = ROOT / "config" / "risk_limits.yaml"


@dataclass(frozen=True)
class RiskLimits:
    max_position_pct: float
    max_gross_exposure_pct: float
    max_open_positions: int
    max_order_notional: float
    max_daily_loss_pct: float
    allow_short: bool


def load_risk_limits(path: Path = RISK_PATH) -> RiskLimits:
    raw = yaml.safe_load(path.read_text()) or {}
    expected = {f.name for f in fields(RiskLimits)}
    missing, unknown = expected - raw.keys(), raw.keys() - expected
    if missing or unknown:
        raise ConfigError(f"{path.name}: missing={sorted(missing)} unknown={sorted(unknown)}")
    limits = RiskLimits(**raw)
    for name in ("max_position_pct", "max_gross_exposure_pct", "max_daily_loss_pct"):
        if not 0 < getattr(limits, name) <= 100:
            raise ConfigError(f"{name} must be in (0, 100]")
    if limits.max_open_positions < 1 or limits.max_order_notional <= 0:
        raise ConfigError("max_open_positions and max_order_notional must be positive")
    return limits
