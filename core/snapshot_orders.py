"""Paper orders for the 15:45-snapshot stock rules (core.snapshot_tracker), placed as market-on-close orders.

Runs on a decision session of a tracked "snapshot" rule with allocation_pct > 0. It loads what it needs
early, waits for the 15:30-15:45 bar to close, ranks the point-in-time S&P 500 members on that 15:45 price
(the same selection code as the shadow record), writes the rule's decision file, and sends the orders that
move the rule's sleeve to the picks (core.sleeves) as market-on-close orders. Alpaca takes those until 15:50
New York time, so nothing is sent after SUBMIT_BY, and a day with no usable 15:45 data sends nothing.

    python -m core.snapshot_orders              # dry run: today's picks and the orders, nothing sent or written
    python -m core.snapshot_orders --execute    # place the orders (paper account, risk limits, journal)

The decision file it writes is the one the 17:10 shadow run reads back (snapshot_1545 and picks), so the
shadow record and the orders follow the same decision. The live 15:45 price comes from the free IEX feed,
the shadow run's own snapshots from the consolidated history, so the two can pick slightly different names
on days the shadow file is written first; the stored file always wins.
"""

import argparse
import json
import sys
import time as clock
from datetime import datetime, time, timezone

import pandas as pd

from core import journal
from core.market_calendar import holidays, trading_days
from core.paper_runner import DataNotReady, PAPER_DIR, _read_json, _write_json, fetch_closes, load_tracked
from core.universe import fetch_membership, load_membership, members_on

NY = "America/New_York"
SNAPSHOT_READY = time(15, 45, 8)    # the 15:30 bar is complete a few seconds after 15:45
SUBMIT_BY = time(15, 49, 30)        # market-on-close cut-off is 15:50
MIN_COVERAGE = 0.9                  # share of members that must have a 15:30 bar, else the day is skipped
LOOKBACK_DAYS = 20


def ny_now() -> pd.Timestamp:
    return pd.Timestamp(datetime.now(timezone.utc)).tz_convert(NY)


def early_close(day: pd.Timestamp) -> bool:
    """Scheduled 13:00 closes: the day after Thanksgiving, Dec 24 and Jul 3 when they are sessions."""
    day = pd.Timestamp(day)
    if (day.month, day.day) in ((12, 24), (7, 3)) and day.weekday() < 5:
        return True
    thanksgiving = [h for h in holidays(day - pd.Timedelta(days=5), day) if h.month == 11 and h.weekday() == 3]
    return bool(thanksgiving) and day == thanksgiving[0] + pd.Timedelta(days=1)


def live_snapshot(symbols, day) -> pd.Series:
    from alpaca.data.enums import DataFeed
    from core.snapshot_tracker import fetch_snapshot
    return fetch_snapshot(symbols, day, feed=DataFeed.IEX)


def decide(rule, sh, snap: pd.Series, base: pd.Series, held: list[str]) -> tuple[list[str], int]:
    """Picks from the 15:45 prices against the close five sessions earlier (the shadow record's signal)."""
    names = [t for t in snap.index if t in base.index and pd.notna(base[t]) and base[t] > 0]
    row = (-(snap.reindex(names) / base.reindex(names) - 1)).dropna()
    return sh.select(rule, row, held), len(row)


def run(execute: bool, only: str | None = None, now_fn=ny_now, sleep_fn=clock.sleep, fetch_closes_fn=fetch_closes,
        snapshot_fn=live_snapshot, membership=None, client=None, out_root=PAPER_DIR, tracked=None) -> int:
    from core import snapshot_tracker as snt

    today = pd.Timestamp(now_fn().date())
    cfgs = [c for c in (tracked if tracked is not None else load_tracked()) if c.get("kind") == "snapshot"
            and (c["rule"] == only if only else c.get("allocation_pct", 0) > 0)]
    if not len(trading_days(today, today)):
        print(f"{today.date()} is not a session; nothing to do")
        return 0
    due = []
    for cfg in cfgs:
        rule, sh = snt.find_rule(cfg["strategy_rule"])
        if rule.get("vix"):
            print(f"{cfg['rule']}: VIX-scaled rules are shadow only; no orders", file=sys.stderr)
            continue
        sessions = snt.decision_sessions(cfg["start"], today, rule["hold"])
        if sessions and sessions[-1] == today:
            due.append((cfg, rule, sh, sessions))
    if not due:
        print(f"{today.date()}: no snapshot rule has a decision today")
        return 0
    if early_close(today):
        for cfg, *_ in due:
            journal.record("skip", f"{today.date()} is an early-close session (market-on-close cut-off is 12:50); no orders for {cfg['rule']}", cfg["rule"])
        print("early close: no orders", file=sys.stderr)
        return 2

    # everything that does not depend on the 15:45 price is loaded first
    if membership is None:
        fetch_membership()
        membership = load_membership()
    members = sorted(members_on(membership, [today])[0])
    base_day = trading_days(today - pd.Timedelta(days=LOOKBACK_DAYS), today)[-6]    # five sessions before today
    closes = fetch_closes_fn(members, today - pd.Timedelta(days=LOOKBACK_DAYS), today - pd.Timedelta(days=1))
    if base_day not in closes.index:
        raise DataNotReady(f"no daily bars for {base_day.date()}")
    base = closes.loc[base_day]

    wait = (pd.Timestamp.combine(today.date(), SNAPSHOT_READY).tz_localize(NY) - now_fn()).total_seconds()
    if wait > 0:
        sleep_fn(wait)

    def late() -> bool:
        return now_fn().time() > SUBMIT_BY

    if late():
        for cfg, *_ in due:
            journal.record("skip", f"missed the market-on-close cut-off on {today.date()} (it was {now_fn().time()} New York)", cfg["rule"])
        print("too late for market-on-close orders; nothing sent", file=sys.stderr)
        return 2
    snap = snapshot_fn(members, today)
    if len(snap) < MIN_COVERAGE * len(members):
        for cfg, *_ in due:
            journal.record("skip", f"only {len(snap)} of {len(members)} members had a 15:30 bar on {today.date()}; no orders", cfg["rule"])
        print(f"snapshot too sparse ({len(snap)} of {len(members)}); nothing sent", file=sys.stderr)
        return 2

    code = 0
    for cfg, rule, sh, sessions in due:
        out_dir = out_root / cfg["rule"]
        stored = _read_json(out_dir, f"decisions/{today.date()}.json")
        if stored is not None:
            picks, source = stored["picks"], "stored decision"
        else:
            previous = _read_json(out_dir, f"decisions/{sessions[-2].date()}.json") if len(sessions) > 1 else None
            held = previous["picks"] if previous else []
            picks, ranked = decide(rule, sh, snap, base, held)
            source = "new decision" if previous or len(sessions) == 1 else "new decision (previous record missing, started flat)"
            if execute:
                _write_json(out_dir, f"decisions/{today.date()}.json", {
                    "decision_date": str(today.date()), "rule": cfg["rule"], "members": len(members), "priced": len(snap),
                    "ranked": ranked, "picks": picks, "weight_each": 1.0 / len(picks) if picks else 0.0,
                    "snapshot_1545": {t: float(snap[t]) for t in sorted(snap.index)}, "closes": {}, "feed": "iex, live"})
        report = {"rule": cfg["rule"], "date": str(today.date()), "source": source, "picks": len(picks),
                  "allocation_pct": cfg["allocation_pct"]}
        if not execute:
            print(json.dumps(report | {"dry_run": True, "picks_list": picks}))
            continue
        from core.paper_runner import place_sleeve_orders
        from alpaca.trading.enums import TimeInForce
        prices = {**closes.ffill().iloc[-1].dropna().to_dict(), **snap.to_dict()}
        result = place_sleeve_orders(
            cfg["rule"], picks, prices, cfg["allocation_pct"], str(today.date()),
            lambda o: f"{cfg['rule']} decision {today.date()} (15:45 price): {'hold' if o['side'] == 'buy' else 'exit'} {o['symbol']}",
            time_in_force=TimeInForce.CLS, client=client, stop_check=late)
        counts = {k: sum(o["result"] == k for o in result["orders"]) for k in ("submitted", "blocked", "late")}
        print(json.dumps(report | counts | {k: result[k] for k in ("skipped", "unpriced") if result.get(k)}))
        if counts["blocked"] or counts["late"] or result.get("skipped"):
            code = 1
    return code


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--execute", action="store_true", help="place the orders and write the decision file (default: dry run)")
    parser.add_argument("--rule", help="only this tracked rule, even if its allocation_pct is 0 (dry runs only)")
    args = parser.parse_args(argv)
    if args.rule and args.execute:
        parser.error("--rule is for dry runs; set allocation_pct in paper/tracked.json to place orders")
    try:
        return run(args.execute, args.rule)
    except DataNotReady as exc:
        print(f"data not ready: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
