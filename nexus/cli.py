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
    p.add_argument("command", choices=["boot", "verify", "lock", "status", "health", "tick", "run", "halt", "resume", "dashboard", "suggest", "growth", "search", "judgment"])
    p.add_argument("--db", default=None, help="override database path")
    p.add_argument("--out", default="data/dashboard/index.html", help="dashboard output path (keep it untracked; it contains holdings)")
    p.add_argument("--fallback-marks", default=None, help="optional JSON {instrument_id: price} used only where the feed has no fresh bar")
    p.add_argument("--snapshot", default=None, help="suggest: owner-confirmed holdings snapshot JSON (private, untracked)")
    p.add_argument("--state", default=None, help="suggest: private state file recording what was last posted")
    p.add_argument("--themes", default=None, help="suggest: optional JSON {symbol: theme}")
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
        elif args.command == "suggest":
            if not (args.snapshot and args.state):
                raise NexusError("suggest needs --snapshot and --state")
            governance.verify_lock()
            from .suggest import run_files
            from .timeutil import utcnow
            print(json.dumps(run_files(args.snapshot, args.state, _data_adapter, utcnow(), args.themes, args.fallback_marks, Store.open(args.db)), indent=2))
        elif args.command == "growth":
            governance.verify_lock()
            from decimal import Decimal
            from .pipeline import daily_growth
            from .timeutil import utcnow
            fb = {k: Decimal(str(v)) for k, v in json.load(open(args.fallback_marks)).items()} if args.fallback_marks else None
            print(json.dumps(daily_growth(Store.open(args.db), _data_adapter(), utcnow(), fb, refresh_clock=True), indent=2))
        elif args.command == "judgment":
            if not (args.snapshot and args.state):
                raise NexusError("judgment needs --snapshot and --state (the calls file)")
            governance.verify_lock()
            from .judgment_run import run_calls_file
            print(json.dumps(run_calls_file(args.snapshot, args.state, _data_adapter, Store.open(args.db), args.themes), indent=2))
        elif args.command == "search":
            governance.verify_lock()
            from .search import digest, run_next
            from .timeutil import utcnow
            out = run_next(Store.open(args.db))
            print(json.dumps({**out, "digest": digest()}, indent=2))
        elif args.command in ("tick", "run", "health", "halt", "resume", "dashboard"):
            return _ops(args)
        else:
            store = Store.open(args.db)
            print(json.dumps({"halted": store.controls.is_halted(), "events": store.events.count(),
                              "stage": permissions.STAGE}))
        return 0
    except NexusError as exc:
        log.error("failing closed: %s", exc)
        return 2


def _data_adapter():
    from .adapters.alpaca_data import AlpacaDataAdapter, data_credentials
    k, s = data_credentials()
    return AlpacaDataAdapter(k, s, derive_symbols=True)


def _jobs():
    from .jobs import default_jobs
    from .adapters.alpaca_data import AlpacaDataAdapter, data_credentials
    def factory():
        k, s = data_credentials()
        return AlpacaDataAdapter(k, s, derive_symbols=True)
    try:
        data_credentials()
        return default_jobs(factory)
    except NexusError:
        return default_jobs(None)            # no data credentials: ingestion/recommendation jobs are not scheduled


def _ops(args) -> int:
    import time
    from .health import report
    from .scheduler import Scheduler
    from .timeutil import utcnow
    governance.verify_lock()
    store = Store.open(args.db)
    jobs = _jobs()
    if args.command == "health":
        rep = report(store, jobs, utcnow())
        print(json.dumps(rep, indent=2))
        return 0 if rep["healthy"] else 1
    if args.command in ("halt", "resume"):
        (store.controls.halt if args.command == "halt" else store.controls.resume)("cli-owner", "via command line")
        print(json.dumps({"halted": store.controls.is_halted()}))
        return 0
    if args.command == "dashboard":
        from decimal import Decimal
        from pathlib import Path
        from .dashboard import render
        fb = {k: Decimal(str(v)) for k, v in json.load(open(args.fallback_marks)).items()} if args.fallback_marks else None
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render(store, jobs, utcnow(), fb), encoding="utf-8")
        print(json.dumps({"written": str(out)}))
        return 0
    sched = Scheduler(store, jobs)
    if args.command == "tick":
        print(json.dumps(sched.tick(utcnow())))
        return 0
    stop = {"flag": False}
    import signal
    signal.signal(signal.SIGTERM, lambda *_: stop.update(flag=True))
    signal.signal(signal.SIGINT, lambda *_: stop.update(flag=True))
    while not stop["flag"]:
        sched.tick(utcnow())
        for _ in range(30):
            if stop["flag"]:
                break
            time.sleep(1)
    return 0
