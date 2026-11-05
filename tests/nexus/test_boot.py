import json

import pytest

from nexus import cli, governance
from nexus.config import load_config


def test_boot_runs_with_no_credentials_and_reports_no_live_authority(tmp_path, monkeypatch, capsys):
    for k in list(__import__("os").environ):
        if any(t in k for t in ("ALPACA", "KEY", "SECRET", "TOKEN")):
            monkeypatch.delenv(k, raising=False)
    out = cli.boot(str(tmp_path / "n.sqlite3"))
    assert out["live_trading"] is False and out["broker_write"] is False and out["stage"] == 0
    assert out["halted"] is False
    assert "base_currency" in out["unconfirmed_owner_inputs"]


def test_boot_twice_keeps_chain_valid(tmp_path):
    db = str(tmp_path / "n.sqlite3")
    cli.boot(db)
    out = cli.boot(db)
    assert out["events_verified_before_boot"] == 2


def test_cli_exit_codes(tmp_path, capsys):
    db = str(tmp_path / "n.sqlite3")
    assert cli.main(["boot", "--db", db]) == 0
    assert cli.main(["verify", "--db", db]) == 0
    assert cli.main(["status", "--db", db]) == 0
    assert json.loads(capsys.readouterr().out.strip().splitlines()[-1])["stage"] == 0


def test_boot_fails_closed_when_governance_drifts(tmp_path, monkeypatch):
    def drift(*a, **k):
        raise governance.GovernanceError("drift")
    monkeypatch.setattr(governance, "verify_lock", drift)
    assert cli.main(["boot", "--db", str(tmp_path / "n.sqlite3")]) == 2
    assert not (tmp_path / "n.sqlite3").exists()  # nothing ran past the failed check


def test_unconfirmed_owner_inputs_listed():
    miss = load_config().unconfirmed_owner_inputs()
    assert "max_acceptable_drawdown" in miss and "risk_limits.owner_limits.max_portfolio_drawdown" in miss


def test_nexus_data_dir_is_gitignored():
    from pathlib import Path
    gi = (Path(__file__).parents[2] / ".gitignore").read_text()
    assert "data/*" in gi
