import ast
from pathlib import Path

import pytest

import nexus
from nexus import permissions
from nexus.config import CONFIG_DIR, load_permissions
from nexus.errors import ConfigError, LaunchBoundaryViolation
from nexus.permissions import Capability

NEXUS_DIR = Path(nexus.__file__).parent
FORBIDDEN_IMPORT_ROOTS = {"alpaca", "alpaca_trade_api", "ib_insync", "ibapi", "ccxt", "robin_stocks", "tda",
                          "schwab", "oandapyV20", "binance", "kalshi", "polymarket",
                          "core", "strategies", "paper", "setups"}  # legacy live/paper code stays isolated


@pytest.mark.parametrize("cap", sorted(permissions.LAUNCH_FORBIDDEN, key=lambda c: c.value))
def test_every_forbidden_capability_is_denied(cap):
    with pytest.raises(LaunchBoundaryViolation):
        permissions.require(cap)
    # even if a config tried to grant it:
    with pytest.raises(LaunchBoundaryViolation):
        permissions.require(cap, narrowed_to=frozenset(Capability))


def test_allowed_capabilities_work_and_config_can_only_narrow():
    permissions.require(Capability.RESEARCH)
    with pytest.raises(LaunchBoundaryViolation):
        permissions.require(Capability.RESEARCH, narrowed_to=frozenset({Capability.BACKTEST}))


def test_unknown_capability_denied():
    with pytest.raises(LaunchBoundaryViolation):
        permissions.require("submit_order")  # type: ignore[arg-type]


def test_forbid_live_always_raises():
    with pytest.raises(LaunchBoundaryViolation):
        permissions.forbid_live("anything")


def _write_perm(tmp_path, **over):
    import shutil, yaml
    d = tmp_path / "cfg"
    shutil.copytree(CONFIG_DIR, d)
    raw = yaml.safe_load((d / "permissions.yaml").read_text())
    raw.update(over)
    (d / "permissions.yaml").write_text(yaml.safe_dump(raw))
    return d


@pytest.mark.parametrize("over", [
    {"live_trading": True}, {"broker_write": True}, {"money_movement": True},
    {"live_trading": "false"}, {"stage": 1}, {"max_instrument_capability_tier": "R4"},
    {"allowed_capabilities": ["research", "submit_real_order"]},
    {"allowed_capabilities": ["research", "nonsense"]},
])
def test_config_cannot_enable_live_authority(tmp_path, over):
    with pytest.raises(ConfigError):
        load_permissions(_write_perm(tmp_path, **over))


def test_shipped_permissions_load():
    p = load_permissions()
    assert p.stage == 0 and not (p.allowed & permissions.LAUNCH_FORBIDDEN)


def _imports(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                yield a.name
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            yield node.module


def test_nexus_never_imports_broker_sdks_or_legacy_trading_code():
    offenders = []
    for py in NEXUS_DIR.rglob("*.py"):
        for mod in _imports(py):
            if mod.split(".")[0] in FORBIDDEN_IMPORT_ROOTS:
                offenders.append(f"{py.relative_to(NEXUS_DIR)}: {mod}")
    assert not offenders, offenders


def test_no_broker_write_verbs_defined_in_nexus():
    verbs = {"submit_order", "place_order", "cancel_order", "replace_order", "withdraw", "transfer_funds"}
    defined = []
    for py in NEXUS_DIR.rglob("*.py"):
        for node in ast.walk(ast.parse(py.read_text(encoding="utf-8"))):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in verbs:
                defined.append(f"{py.name}:{node.name}")
    assert not defined, defined
