"""Typed, validated configuration loading. Fails closed on anything suspicious."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from . import permissions
from .domain.enums import CapabilityTier
from .errors import ConfigError
from .paper_guard import PAPER_ENDPOINT
from .secrets import scan_text_for_secrets

CONFIG_DIR = Path(__file__).parent / "config"
GOVERNED_FILES = ("permissions.yaml", "risk_limits.yaml", "promotion_criteria.yaml")


def _load_yaml(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    found = scan_text_for_secrets(text)
    if found:
        raise ConfigError(f"{path.name}: secret-like content detected ({', '.join(found)}); "
                          "secrets must come from the environment")
    data = yaml.safe_load(text) or {}
    if not isinstance(data, dict):
        raise ConfigError(f"{path.name}: top level must be a mapping")
    return data


@dataclass(frozen=True)
class Permissions:
    stage: int
    max_tier: CapabilityTier
    allowed: frozenset[permissions.Capability]


@dataclass(frozen=True)
class AppConfig:
    environment: str
    database_path: str
    clock_skew_tolerance_seconds: float
    owner_inputs: dict[str, Any]
    risk_limits: dict[str, Any]
    promotion: dict[str, Any]
    permissions: Permissions

    def unconfirmed_owner_inputs(self) -> list[str]:
        """Owner inputs still null. Features depending on them must stay disabled."""
        missing = [k for k, v in self.owner_inputs.items() if v is None]
        for group in ("owner_limits",):
            missing += [f"risk_limits.{group}.{k}" for k, v in self.risk_limits.get(group, {}).items() if v is None]
        return sorted(missing)


def load_permissions(config_dir: Path = CONFIG_DIR) -> Permissions:
    raw = _load_yaml(config_dir / "permissions.yaml")
    if raw.get("stage") != permissions.STAGE:
        raise ConfigError(f"permissions.yaml stage {raw.get('stage')!r} != code stage {permissions.STAGE}")
    for flag in ("live_trading", "broker_write", "money_movement"):
        if raw.get(flag) is not False:  # must be literally False; missing/true/"false" all rejected
            raise ConfigError(f"permissions.yaml: '{flag}' must be false at Stage {permissions.STAGE}")
    try:
        tier = CapabilityTier(raw.get("max_instrument_capability_tier"))
    except ValueError as exc:
        raise ConfigError("permissions.yaml: invalid max_instrument_capability_tier") from exc
    if tier == CapabilityTier.R4:
        raise ConfigError("R4 (future live eligible) is unavailable at launch")
    caps = set()
    for name in raw.get("allowed_capabilities", []):
        try:
            cap = permissions.Capability(name)
        except ValueError as exc:
            raise ConfigError(f"permissions.yaml: unknown capability {name!r}") from exc
        if cap in permissions.LAUNCH_FORBIDDEN:
            raise ConfigError(f"permissions.yaml: capability '{name}' is forbidden at launch")
        caps.add(cap)
    if permissions.Capability.PAPER_BROKER_ORDER in caps:
        auth = raw.get("paper_broker_authorization") or {}
        if not (auth.get("granted_by") and auth.get("granted_at") and auth.get("endpoint") == PAPER_ENDPOINT):
            raise ConfigError("paper_broker_order requires a recorded owner authorization pinned to the paper endpoint")
    return Permissions(stage=raw["stage"], max_tier=tier, allowed=frozenset(caps))


def load_config(config_dir: Path = CONFIG_DIR) -> AppConfig:
    app_raw = _load_yaml(config_dir / "app.yaml")
    app = app_raw.get("app") or {}
    if app.get("stage") != permissions.STAGE:
        raise ConfigError("app.yaml stage does not match the code's launch stage")
    skew = app.get("clock_skew_tolerance_seconds")
    if not isinstance(skew, (int, float)) or isinstance(skew, bool) or skew < 0:
        raise ConfigError("app.yaml: clock_skew_tolerance_seconds must be a non-negative number")
    # Load every other file too so a malformed/secret-bearing one fails the boot.
    _load_yaml(config_dir / "data_sources.yaml")
    return AppConfig(
        environment=str(app.get("environment", "development")),
        database_path=str(app.get("database_path", "data/nexus.sqlite3")),
        clock_skew_tolerance_seconds=float(skew),
        owner_inputs=dict(app_raw.get("owner_inputs") or {}),
        risk_limits=_load_yaml(config_dir / "risk_limits.yaml"),
        promotion=_load_yaml(config_dir / "promotion_criteria.yaml"),
        permissions=load_permissions(config_dir),
    )
