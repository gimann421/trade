import shutil

import pytest

from nexus import governance
from nexus.config import CONFIG_DIR
from nexus.errors import GovernanceError


def test_shipped_lock_verifies():
    assert governance.verify_lock()


@pytest.mark.parametrize("fname", ["permissions.yaml", "risk_limits.yaml", "promotion_criteria.yaml"])
def test_editing_governed_config_is_detected(tmp_path, fname):
    d = tmp_path / "cfg"
    shutil.copytree(CONFIG_DIR, d)
    lock = tmp_path / "lock.json"
    governance.write_lock(lock, config_dir=d)
    governance.verify_lock(lock, config_dir=d)
    (d / fname).write_text((d / fname).read_text() + "\n# tampered\n")
    with pytest.raises(GovernanceError, match=fname):
        governance.verify_lock(lock, config_dir=d)


def test_editing_constitution_is_detected(tmp_path):
    c = tmp_path / "c.md"
    c.write_text("rules")
    lock = tmp_path / "lock.json"
    governance.write_lock(lock, constitution=c)
    c.write_text("weaker rules")
    with pytest.raises(GovernanceError):
        governance.verify_lock(lock, constitution=c)


def test_missing_lock_fails_closed(tmp_path):
    with pytest.raises(GovernanceError):
        governance.verify_lock(tmp_path / "nope.json")


def test_governed_files_not_in_agent_memory(tmp_path):
    governance.assert_memory_is_clean()
    mem = tmp_path / "mem"
    mem.mkdir()
    (mem / "risk_limits.yaml").write_text("x")
    with pytest.raises(GovernanceError):
        governance.assert_memory_is_clean(mem)


def test_line_ending_normalization(tmp_path):
    c = tmp_path / "c.md"
    c.write_bytes(b"a\nb\n")
    h1 = governance._sha256(c)
    c.write_bytes(b"a\r\nb\r\n")
    assert governance._sha256(c) == h1
