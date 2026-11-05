import pytest

from nexus import permissions
from nexus.config import load_config, load_permissions
from nexus.errors import ConfigError, LaunchBoundaryViolation, SecretError
from nexus.paper_guard import assert_paper_endpoint, paper_credentials



def _write_perm(tmp_path, **over):
    import shutil, yaml
    from nexus.config import CONFIG_DIR
    d = tmp_path / "cfg"
    shutil.copytree(CONFIG_DIR, d)
    raw = yaml.safe_load((d / "permissions.yaml").read_text())
    raw.update(over)
    (d / "permissions.yaml").write_text(yaml.safe_dump(raw))
    return d


def test_paper_endpoint_accepted():
    assert_paper_endpoint("https://paper-api.alpaca.markets/v2/orders")


@pytest.mark.parametrize("url", [
    "https://api.alpaca.markets/v2/orders", "http://paper-api.alpaca.markets/v2/orders",
    "https://paper-api.alpaca.markets.evil.com/v2/orders", "https://evil.com/paper-api.alpaca.markets",
    "https://user:pw@paper-api.alpaca.markets/", "https://paper-api.alpaca.markets:8443/", "", "paper-api.alpaca.markets",
])
def test_everything_else_refused(url):
    with pytest.raises(LaunchBoundaryViolation):
        assert_paper_endpoint(url)


def test_live_capabilities_still_forbidden_with_paper_authorized():
    cfg = load_config()
    assert permissions.is_allowed(permissions.Capability.PAPER_BROKER_ORDER, cfg.permissions.allowed)
    for cap in (permissions.Capability.BROKER_WRITE, permissions.Capability.SUBMIT_REAL_ORDER,
                permissions.Capability.MOVE_MONEY, permissions.Capability.WITHDRAW):
        assert not permissions.is_allowed(cap, cfg.permissions.allowed)


def test_credentials_env_only_and_masked():
    allowed = load_config().permissions.allowed
    env = {"NEXUS_ALPACA_PAPER_KEY_ID": "idvalue123456", "NEXUS_ALPACA_PAPER_SECRET_KEY": "secretvalue123456"}
    k, s = paper_credentials(allowed, env)
    assert "idvalue" not in repr(k) and "secretvalue" not in repr(s)
    with pytest.raises(SecretError):
        paper_credentials(allowed, {})


def test_credentials_denied_if_capability_not_granted():
    with pytest.raises(LaunchBoundaryViolation):
        paper_credentials(frozenset({permissions.Capability.RESEARCH}), {})


def test_config_needs_recorded_authorization_and_pinned_endpoint(tmp_path):
    for bad in ({"paper_broker_authorization": None},
                {"paper_broker_authorization": {"granted_by": "x", "granted_at": "t", "endpoint": "https://api.alpaca.markets"}}):
        with pytest.raises(ConfigError):
            load_permissions(_write_perm(tmp_path / str(len(str(bad))), **bad))
