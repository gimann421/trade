"""Command line: ``python -m nexus {boot,verify,lock,status}``. Boots with zero credentials."""
from __future__ import annotations

import argparse
import json
import sys

from . import __version__, governance, permissions
from .config import load_config
from .domain.enums import EventType
from .errors import NexusError
from .logs import get_logger
from .store import Store


def boot(db_path: str | None = None) -> dict:
    """Verify governance + config + audit chain, run migrations, record the boot. Fails closed."""
    governance.verify_lock()
    governance.assert_memory_is_clean()
    cfg = load_config()
    store = Store.open(db_path, cfg)
    n = store.events.verify_chain()
    store.events.append(EventType.GOVERNANCE_VERIFIED, "governance", "system",
                        {"files": governance.compute_manifest()})
    store.events.append(EventType.SYSTEM_BOOT, "cli", "system",
                        {"version": __version__, "stage": permissions.STAGE})
    return {"version": __version__, "stage": permissions.STAGE, "live_trading": False,
            "broker_write": False, "events_verified_before_boot": n,
            "halted": store.controls.is_halted(),
            "unconfirmed_owner_inputs": cfg.unconfirmed_owner_inputs()}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="nexus")
    p.add_argument("command", choices=["boot", "verify", "lock", "status"])
    p.add_argument("--db", default=None, help="override database path")
    args = p.parse_args(argv)
    log = get_logger()
    try:
        if args.command == "boot":
            print(json.dumps(boot(args.db), indent=2))
        elif args.command == "verify":
            governance.verify_lock()
            cfg = load_config()
            n = Store.open(args.db, cfg).events.verify_chain()
            print(json.dumps({"governance": "ok", "audit_events_verified": n}))
        elif args.command == "lock":
            print(json.dumps(governance.write_lock(), indent=2))
            print("governance.lock.json rewritten - review the diff and get owner approval before committing.",
                  file=sys.stderr)
        else:
            store = Store.open(args.db)
            print(json.dumps({"halted": store.controls.is_halted(), "events": store.events.count(),
                              "stage": permissions.STAGE}))
        return 0
    except NexusError as exc:
        log.error("failing closed: %s", exc)
        return 2
