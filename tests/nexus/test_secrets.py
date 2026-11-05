import json
import logging
from pathlib import Path

import pytest

import nexus
from nexus.config import CONFIG_DIR, load_config
from nexus.errors import ConfigError, SecretError
from nexus.logs import RedactingJsonFormatter
from nexus.secrets import Secret, get_secret, redact, scan_text_for_secrets

FAKE_ALPACA = "PK" + "ABCDEFGHIJKLMNOPQRST"
FAKE_ASSIGN = "api_key" + ": " + "abcdef1234567890xyz"


def test_secret_repr_and_format_are_masked():
    s = Secret("BROKER_KEY", "supersecretvalue123")
    assert "supersecret" not in repr(s) and "supersecret" not in str(s) and "supersecret" not in f"{s}"
    assert s.reveal() == "supersecretvalue123"


def test_secret_cannot_be_pickled():
    import pickle
    with pytest.raises(SecretError):
        pickle.dumps(Secret("X", "valuevalue123"))


def test_get_secret_from_env_only_and_missing_fails():
    assert get_secret("K", {"K": "valuevalue1"}).reveal() == "valuevalue1"
    with pytest.raises(SecretError):
        get_secret("K", {})


def test_scanner_finds_patterns_without_returning_values():
    assert "alpaca_key" in scan_text_for_secrets(f"x {FAKE_ALPACA} y")
    assert scan_text_for_secrets(FAKE_ASSIGN)
    assert scan_text_for_secrets("just a normal sentence") == []


def test_logging_redacts_registered_values_and_patterns():
    Secret("S", "my-registered-secret-9999")
    rec = logging.LogRecord("n", logging.INFO, "f", 1, "value=%s key=%s", ("my-registered-secret-9999", FAKE_ALPACA), None)
    out = RedactingJsonFormatter().format(rec)
    assert "my-registered-secret-9999" not in out and FAKE_ALPACA not in out and "[REDACTED]" in out
    json.loads(out)


def test_config_with_secret_is_rejected(tmp_path):
    import shutil
    d = tmp_path / "cfg"
    shutil.copytree(CONFIG_DIR, d)
    (d / "app.yaml").write_text((d / "app.yaml").read_text() + f"\n# {FAKE_ASSIGN}\n")
    with pytest.raises(ConfigError):
        load_config(d)


def test_audit_log_refuses_secrets(store):
    from nexus.domain.enums import EventType
    with pytest.raises(SecretError):
        store.events.append(EventType.SYSTEM_BOOT, "t", "t", {"note": FAKE_ALPACA})
    assert store.events.count() == 0


def test_no_secrets_in_repo_nexus_files():
    root = Path(nexus.__file__).parent
    hits = []
    for p in list(root.rglob("*")) + list((root.parent / "tests" / "nexus").rglob("*")):
        if p.is_file() and p.suffix in {".py", ".yaml", ".md", ".sql", ".json"}:
            found = scan_text_for_secrets(p.read_text(encoding="utf-8"))
            # docs may mention the words 'token'/'password' in prose but never as assignments
            if found:
                hits.append((str(p.relative_to(root.parent)), found))
    assert not hits, hits
