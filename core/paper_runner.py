"""Forward record for rules that passed the research bar: a shadow portfolio, run once per trading day.

The runner never needs yesterday's container: each run rebuilds the shadow portfolio from the rule's
start date on freshly downloaded bars, with the same code the backtest used, and writes
paper/<rule id>/ (nav.csv, status.json, one decisions/<date>.json per month-end). A decision file is
written once and never overwritten: later runs recompute the picks and flag any difference, so the
record shows what was decided at the time. By default nothing is sent to a broker. Orders are only
considered with --execute, and only for rules whose allocation_pct in paper/tracked.json is above 0;
they go through core.broker.submit_order (paper account, risk limits, journal).

    python -m core.paper_runner preview stock_resmom6_1_decile   # picks as of the latest month-end
    python -m core.paper_runner run                              # update every tracked rule (dry)
    python -m core.paper_runner run --execute                    # also place paper orders (see above)
    python -m core.paper_runner plan stock_resmom6_1_decile      # the orders --execute would place, checked against the risk limits; sends nothing
"""

import argparse
import importlib.util
import json
import math
import sys
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from core.config import ROOT
from core.market_calendar import trading_days
from core.portfolio import month_ends, simulate
from core.universe import fetch_membership, load_membership, members_on

PAPER_DIR = ROOT / "paper"
TRACKED_PATH = PAPER_DIR / "tracked.json"
COST_BPS = 5.0
HISTORY_DAYS = 420          # calendar days of history before the start date (covers the 126-day signal)
FACTOR_ETFS = ("VTI", "BIL", "IWM", "IWB", "IWD", "IWF")


class DataNotReady(RuntimeError):
    pass


# --- dates --------------------------------------------------------------------------------

def last_completed_session(now: datetime | None = None) -> pd.Timestamp:
    """The latest scheduled session whose 16:00 New York close has passed."""
    now = pd.Timestamp(now or datetime.now(timezone.utc))
    now = now.tz_localize("UTC") if now.tzinfo is None else now
    ny = now.tz_convert("America/New_York")
    today = pd.Timestamp(ny.date())
    days = trading_days(today - pd.Timedelta(days=14), today)
    if ny.time() < time(16, 0):
        days = days[days < today]
    return days[-1]


def decision_dates(start, end) -> list[pd.Timestamp]:
    """Scheduled month-end sessions in [start, end], from the exchange calendar alone."""
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    days = trading_days(start - pd.Timedelta(days=5), end + pd.Timedelta(days=15))
    return [d for d in days[month_ends(days)] if start <= d <= end]


# --- data ---------------------------------------------------------------------------------

def fetch_closes(symbols, start, end, client=None, batch: int = 100) -> pd.DataFrame:
    """Adjusted daily closes for the symbols, one column each (symbols without bars are absent)."""
    from alpaca.data.enums import Adjustment
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame
    from core.config import load_paper_keys

    if client is None:
        keys = load_paper_keys()
        client = StockHistoricalDataClient(keys.api_key, keys.secret_key)
    symbols = sorted(set(symbols))
    frames = []
    # the free plan rejects the most recent 15 minutes of data
    request_end = min(pd.Timestamp(end) + pd.Timedelta(days=2), pd.Timestamp.now("UTC").tz_localize(None) - pd.Timedelta(minutes=20))
    for i in range(0, len(symbols), batch):
        request = StockBarsRequest(symbol_or_symbols=symbols[i:i + batch], timeframe=TimeFrame.Day,
                                   start=pd.Timestamp(start).to_pydatetime().replace(tzinfo=timezone.utc),
                                   end=request_end.to_pydatetime().replace(tzinfo=timezone.utc),
                                   adjustment=Adjustment.ALL)
        df = client.get_stock_bars(request).df
        if not df.empty:
            frames.append(df["close"].unstack("symbol") if isinstance(df.index, pd.MultiIndex) else df[["close"]])
    if not frames:
        raise DataNotReady("no bars returned")
    closes = pd.concat(frames, axis=1)
    closes.index = pd.DatetimeIndex(pd.to_datetime(closes.index).tz_convert("America/New_York").date)
    return closes.sort_index().loc[:pd.Timestamp(end)]


def load_module(name: str):
    path = ROOT / "strategies" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --- one rule ------------------------------------------------------------------------------

def run_rule(cfg: dict, session: pd.Timestamp, membership: pd.Series, fetch, out_dir: Path | None, fs=None, rm=None) -> dict:
    """Update the shadow record of one tracked rule up to `session`. out_dir=None writes nothing."""
    fs, rm = fs or load_module("factor_scan_v1"), rm or load_module("residual_momentum_v1")
    rule = next((r for r in fs.RULES if r["id"] == cfg["rule"]), None)
    if rule is None or rule["family"] != "stock" or rule["signal"] != "resmom6_1" or rule.get("trend"):
        raise ValueError(f"{cfg['rule']}: the runner supports the resmom6_1 stock rules only")
    start = pd.Timestamp(cfg["start"])
    decisions = decision_dates(start, session)
    status = {"rule": cfg["rule"], "asof": str(session.date()), "start": str(start.date()),
              "membership_last_row": str(membership.index[-1].date())}
    if not decisions:
        status |= {"state": "waiting", "first_decision": str(decision_dates(start, start + pd.Timedelta(days=40))[0].date())}
        _write_json(out_dir, "status.json", status)
        return status

    members = sorted(frozenset().union(*members_on(membership, decisions)))
    closes = fetch(members + list(FACTOR_ETFS), start - pd.Timedelta(days=HISTORY_DAYS), session)
    missing_etf = [s for s in FACTOR_ETFS if s not in closes.columns]
    if missing_etf:
        raise DataNotReady(f"no bars for {missing_etf}")
    index = closes["VTI"].dropna().index
    if index[-1] < session:
        raise DataNotReady(f"latest bar is {index[-1].date()}, but the last completed session is {session.date()}")
    stocks = closes.reindex(index)[[c for c in members if c in closes.columns]]
    etf = closes.reindex(index)[list(FACTOR_ETFS)]
    if etf.isna().any().any():
        raise DataNotReady("factor ETF bars have gaps")
    status["members_without_bars"] = sorted(set(members) - set(stocks.columns))

    returns, factors = stocks.pct_change(fill_method=None), rm.factor_returns(etf)
    scores = pd.DataFrame(np.nan, index, stocks.columns)
    for date in decisions:
        if date not in index:
            raise DataNotReady(f"no bar for decision date {date.date()}")
        priced = [t for t in sorted(members_on(membership, [date])[0]) if t in stocks.columns and pd.notna(stocks.at[date, t])]
        scores.loc[date, priced] = rm.residual_scores(returns, factors, index.get_loc(date), priced,
                                                      **fs.RESMOM6_1).reindex(priced).to_numpy()
    close_raw = stocks.copy()
    close_raw[fs.CASH] = etf[fs.CASH]
    scores[fs.CASH] = np.nan
    saved = fs.FIRST_DECISION
    fs.FIRST_DECISION = str(start.date())
    try:
        targets, bench_targets, detail = fs.generate_targets(rule, close_raw, scores, decisions, membership)
    finally:
        fs.FIRST_DECISION = saved

    first = detail[0]["date"]
    close_ff = close_raw.ffill().loc[first:]
    initial = float(cfg.get("initial_cash", 100_000))
    run = simulate(close_ff, targets.loc[first:], COST_BPS)
    bench = simulate(close_ff, bench_targets.loc[first:], COST_BPS)
    nav = pd.DataFrame({"nav": initial * (1 + run["returns"]).cumprod(),
                        "benchmark_nav": initial * (1 + bench["returns"]).cumprod(),
                        "invested": run["held"]})
    nav.index.name = "date"

    changed = []
    for d in detail:
        record = {"decision_date": str(d["date"].date()), "rule": cfg["rule"], "members": d["members"],
                  "priced": len(d["priced"]), "ranked": len(d["ranked"]),
                  "picks": d["picks"], "weight_each": 1.0 / len(d["picks"]) if d["picks"] else 0.0,
                  "closes": {t: float(close_raw.at[d["date"], t]) for t in d["picks"]}}
        existing = _read_json(out_dir, f"decisions/{d['date'].date()}.json")
        if existing is None:
            _write_json(out_dir, f"decisions/{d['date'].date()}.json", record)
        elif sorted(existing["picks"]) != sorted(record["picks"]):
            changed.append({"decision_date": record["decision_date"], "stored_only": sorted(set(existing["picks"]) - set(record["picks"])),
                            "recomputed_only": sorted(set(record["picks"]) - set(existing["picks"]))})
    last = detail[-1]
    status |= {"state": "running", "first_decision": str(first.date()), "last_decision": str(last["date"].date()),
               "decisions": len(detail), "nav": float(nav["nav"].iloc[-1]), "benchmark_nav": float(nav["benchmark_nav"].iloc[-1]),
               "excess_return": float(nav["nav"].iloc[-1] / nav["benchmark_nav"].iloc[-1] - 1),
               "total_return": float(nav["nav"].iloc[-1] / initial - 1),
               "holdings": last["picks"], "decisions_changed_since_recorded": changed}
    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        nav.to_csv(out_dir / "nav.csv")
    _write_json(out_dir, "status.json", status)
    return status


def _write_json(out_dir, name, obj):
    if out_dir is None:
        return
    path = out_dir / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, sort_keys=True) + "\n")


def _read_json(out_dir, name):
    if out_dir is None or not (out_dir / name).exists():
        return None
    return json.loads((out_dir / name).read_text())


# --- orders (only used with --execute) ----------------------------------------------------

def plan_orders(picks: list[str], prices: dict[str, float], positions: dict[str, float], managed: set[str],
                budget: float) -> list[dict]:
    """Whole-share orders that move the managed positions to an equal-weight book of `budget` dollars.
    Each pick is sized to the nearest whole share, but never below one share, so names priced above the
    per-name budget are still held (slightly overweight) instead of silently dropping out.

    positions: symbol -> shares currently held in the account. Only symbols in `managed` (names the
    rule has held or holds) are touched; anything else in the account is left alone. Sells first.
    """
    each = budget / len(picks) if picks else 0.0
    orders = []
    for symbol in sorted(managed | set(picks)):
        price = prices.get(symbol)
        if not price or price <= 0:
            continue
        target = max(1, math.floor(each / price + 0.5)) if symbol in picks else 0
        delta = target - int(round(positions.get(symbol, 0.0)))
        if delta:
            orders.append({"symbol": symbol, "side": "buy" if delta > 0 else "sell", "qty": abs(delta), "price": float(price)})
    return sorted(orders, key=lambda o: (o["side"] != "sell", o["symbol"]))


def check_plan(orders: list[dict], state, limits) -> list[dict]:
    """Run planned orders through the risk check one after another, as they would go in. Sends nothing.
    Each order comes back with the list of limits it would break (empty = it may go)."""
    from core.risk import AccountState, ProposedOrder, check_order

    positions, shares = dict(state.positions), dict(getattr(state, "shares", {}))
    checked = []
    for o in orders:
        order = ProposedOrder(o["symbol"], o["side"], o["qty"], o["price"])
        violations = check_order(order, AccountState(state.equity, state.day_start_equity, dict(positions), dict(shares)), limits)
        checked.append(o | {"violations": violations})
        if not violations:
            positions[o["symbol"]] = positions.get(o["symbol"], 0.0) + order.signed_notional
            if o["symbol"] in shares:
                shares[o["symbol"]] += o["qty"] if o["side"] == "buy" else -o["qty"]
    return checked


def place_sleeve_orders(rule: str, picks: list[str], prices: dict[str, float], allocation_pct: float, label: str,
                        reasoning, hypothesis_id: int | None = None, time_in_force=None, client=None, stop_check=None) -> dict:
    """Move the rule's sleeve (its own shares, found through core.sleeves) to an equal-weight book of
    allocation_pct of account equity, as risk-checked, journaled paper orders tagged with the rule.

    label is the decision date in each order's client_order_id; reasoning(order) gives the journal text.
    stop_check() is asked before each order; once it returns True the rest are listed as "late" and not sent.
    Nothing is sent while an earlier order of the rule is still open. Orders that fail the risk check
    come back as "blocked"; names with no price are listed in "unpriced" and left alone.

    One bad order never ends the run. Alpaca rejects an order as a possible wash trade while another open order
    (usually another rule's slice) sits on the opposite side of the same symbol; such orders are not sent and come
    back as "deferred". Any other order the broker refuses comes back as "error" with the message. Because the
    plan is rebuilt from the sleeve's filled shares, the next run (the 09:36 catch-up) sends whatever is still
    missing, and an order id that was already used gets a "retryN" suffix so it can be sent again."""
    from alpaca.trading.enums import TimeInForce
    from core.broker import RiskViolation, account_state, get_paper_client, submit_order
    from core.risk import ProposedOrder
    from alpaca.trading.enums import QueryOrderStatus
    from alpaca.trading.requests import GetOrdersRequest
    from core.sleeves import SEP, _side, open_orders, order_tag, rule_orders, sleeve_shares

    client = client or get_paper_client()
    history = rule_orders(client, rule)
    pending = open_orders(history)
    if pending:
        return {"orders": [], "skipped": f"{len(pending)} earlier order(s) of this rule are still open", "unpriced": []}
    shares = sleeve_shares(history)
    used_ids = {str(o.client_order_id) for o in history}
    try:
        other_open = {}
        for o in open_orders(client.get_orders(GetOrdersRequest(status=QueryOrderStatus.OPEN, limit=500))):
            other_open.setdefault(o.symbol, set()).add(_side(o))
    except Exception:
        other_open = {}                       # the broker's own wash check still applies; it is handled per order below
    state = account_state(client)
    unpriced = sorted(s for s in set(picks) | set(shares) if not prices.get(s))
    orders = plan_orders(picks, prices, shares, set(shares), state.equity * allocation_pct / 100.0)
    results = []
    for o in orders:
        tif = time_in_force() if callable(time_in_force) else time_in_force
        if stop_check and stop_check():
            results.append(o | {"result": "late"})
            continue
        opposite = "sell" if o["side"] == "buy" else "buy"
        if opposite in other_open.get(o["symbol"], ()):
            results.append(o | {"result": "deferred", "reason": f"another open order is on the {opposite} side of {o['symbol']} (wash-trade rule)"})
            continue
        tag = order_tag(rule, label, o["symbol"], o["side"])
        attempt = 1
        while tag in used_ids:
            attempt += 1
            tag = order_tag(rule, label, o["symbol"], o["side"]) + f"{SEP}retry{attempt}"
        try:
            submit_order(client, ProposedOrder(o["symbol"], o["side"], o["qty"], o["price"]), reasoning(o), rule,
                         hypothesis_id=hypothesis_id, time_in_force=tif or TimeInForce.DAY, client_order_id=tag)
            used_ids.add(tag)
            results.append(o | {"result": "submitted", "tif": str(getattr(tif, "value", tif or "day"))})
        except RiskViolation as exc:
            results.append(o | {"result": "blocked", "violations": exc.violations})
        except Exception as exc:              # a refused order (wash trade, halted name, ...) must not stop the rest
            reason = f"{type(exc).__name__}: {exc}"
            kind = "deferred" if "wash" in reason.lower() else "error"
            results.append(o | {"result": kind, "reason": reason})
    return {"orders": results, "unpriced": unpriced, "sleeve_symbols": len(shares), "equity": state.equity}


def execute_orders(cfg: dict, status: dict, closes_by_symbol: dict[str, float], hypothesis_id: int | None) -> dict:
    """Month-end stock rules: the planned orders as DAY market orders placed after the close."""
    return place_sleeve_orders(
        cfg["rule"], status["holdings"], closes_by_symbol, cfg["allocation_pct"], status["last_decision"],
        lambda o: (f"{cfg['rule']} month-end rebalance decided {status['last_decision']}: "
                   f"{'hold' if o['side'] == 'buy' else 'exit'} {o['symbol']} (equal-weight picks of the rule's residual momentum ranking)"),
        hypothesis_id)


def execute_signal_orders(cfg: dict, status: dict, price: float, session: pd.Timestamp) -> dict:
    """Single-symbol signal rules: hold the symbol while the rule is in position, else be flat.
    DAY market orders placed after the close, so they fill at the next open (the shadow record assumes the close)."""
    picks = [cfg["symbol"]] if status.get("in_position") else []
    return place_sleeve_orders(
        cfg["rule"], picks, {cfg["symbol"]: price}, cfg["allocation_pct"], str(session.date()),
        lambda o: (f"{cfg['rule']} signal as of the {session.date()} close: "
                   f"{'in position' if status.get('in_position') else 'flat'}, {o['side']} {o['symbol']} to match"))


# --- command line -------------------------------------------------------------------------

def load_tracked() -> list[dict]:
    return json.loads(TRACKED_PATH.read_text())["tracked"]


def hypothesis_id(rule_id: str) -> int | None:
    from core.ledger import connect
    conn = connect()
    row = conn.execute("SELECT id FROM hypotheses WHERE title = ?", (f"Scan v1: {rule_id}",)).fetchone()
    conn.close()
    return row[0] if row else None


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    pre = sub.add_parser("preview", help="picks as of the latest month-end; writes nothing")
    pre.add_argument("rule")
    plan = sub.add_parser("plan", help="the orders --execute would place, risk-checked; sends nothing")
    plan.add_argument("rule")
    plan.add_argument("--allocation", type=float, help="percent of account equity (default: the rule's allocation_pct, else 50)")
    run = sub.add_parser("run", help="update every tracked rule")
    run.add_argument("--execute", action="store_true", help="also place paper orders (needs allocation_pct > 0)")
    run.add_argument("--execute-kinds", default="stock,signal",
                     help="with --execute, which rule kinds may place orders: stock (month-end rules), signal (single-symbol rules)")
    args = parser.parse_args(argv)

    session = last_completed_session()
    fetch_membership()
    membership = load_membership()
    if args.command == "preview":
        latest = decision_dates(session - pd.Timedelta(days=45), session)[-1]
        status = run_rule({"rule": args.rule, "start": str(latest.date())}, session, membership, fetch_closes, None)
        print(json.dumps({k: status[k] for k in ("rule", "asof", "last_decision", "holdings", "members_without_bars") if k in status}, indent=1))
        return 0

    if args.command == "plan":
        from core.broker import account_state, get_paper_client
        from core.risk import load_risk_limits

        cfg = next((c for c in load_tracked() if c["rule"] == args.rule), {})
        allocation = args.allocation if args.allocation is not None else (cfg.get("allocation_pct") or 50.0)
        latest = decision_dates(session - pd.Timedelta(days=45), session)[-1]
        status = run_rule({"rule": args.rule, "start": str(latest.date())}, session, membership, fetch_closes, None)
        from core.sleeves import rule_orders, sleeve_shares
        client = get_paper_client()
        state, limits = account_state(client), load_risk_limits()
        held = sleeve_shares(rule_orders(client, args.rule))
        managed = set(held)
        prices = fetch_closes(sorted(set(status["holdings"]) | managed), session - pd.Timedelta(days=10), session).iloc[-1].to_dict()
        checked = check_plan(plan_orders(status["holdings"], prices, held, managed, state.equity * allocation / 100), state, limits)
        blocked = [o for o in checked if o["violations"]]
        reasons = sorted({v.split(" (")[0].split(" would")[0] if "max_open" in v else v[:90] for o in blocked for v in o["violations"]})
        print(json.dumps({"rule": args.rule, "decision": status["last_decision"], "equity": state.equity, "allocation_pct": allocation,
                          "orders": len(checked), "buys": sum(o["side"] == "buy" for o in checked),
                          "sells": sum(o["side"] == "sell" for o in checked),
                          "buy_notional": round(sum(o["qty"] * o["price"] for o in checked if o["side"] == "buy"), 2),
                          "blocked_by_limits": len(blocked), "reasons": reasons[:6],
                          "limits": {k: getattr(limits, k) for k in ("max_position_pct", "max_gross_exposure_pct", "max_open_positions",
                                                                     "max_order_notional", "max_daily_loss_pct")}}, indent=1))
        return 0

    failures = 0
    kinds = set(args.execute_kinds.split(","))
    for cfg in load_tracked():
        if cfg.get("kind") == "snapshot":
            from core import snapshot_tracker as snt
            try:
                status = snt.run_snapshot_rule(cfg, session, membership, PAPER_DIR / cfg["rule"])
            except DataNotReady as exc:
                print(f"{cfg['rule']}: data not ready ({exc})", file=sys.stderr)
                failures += 1
                continue
            print(cfg["rule"], json.dumps({k: status.get(k) for k in ("state", "asof", "last_decision", "nav", "benchmark_nav", "excess_return")}))
            if status.get("decisions_changed_since_recorded"):
                print(f"  WARNING: recomputed picks differ from the recorded decisions: {status['decisions_changed_since_recorded']}", file=sys.stderr)
            if args.execute and cfg.get("allocation_pct", 0) > 0:
                print(f"  {cfg['rule']}: snapshot rules place their orders before the close (python -m core.snapshot_orders), not here", file=sys.stderr)
            continue
        if cfg.get("kind") == "signal":
            from core import signal_tracker as st
            try:
                bars = st.fetch_bars(cfg["symbol"], pd.Timestamp(cfg["start"]) - pd.Timedelta(days=st.HISTORY_DAYS), session)
                status = st.run_signal_rule(cfg, session, bars, PAPER_DIR / cfg["rule"])
            except DataNotReady as exc:
                print(f"{cfg['rule']}: data not ready ({exc})", file=sys.stderr)
                failures += 1
                continue
            print(cfg["rule"], json.dumps({k: status.get(k) for k in ("state", "asof", "nav", "benchmark_nav", "excess_return", "entries", "in_position")}))
            if status.get("decisions_changed_since_recorded"):
                print(f"  WARNING: recomputed signals differ from the recorded ones: {status['decisions_changed_since_recorded']}", file=sys.stderr)
            if args.execute and "signal" in kinds and cfg.get("allocation_pct", 0) > 0 and status.get("state") == "running" \
                    and status.get("asof") == str(session.date()):
                result = execute_signal_orders(cfg, status, float(bars["close"].iloc[-1]), session)
                print("  orders", json.dumps(result))
            continue
        if cfg.get("kind") == "accruals":
            from core import accruals_tracker as at
            try:
                status = at.run_accruals_rule(cfg, session, membership, fetch_closes, PAPER_DIR / cfg["rule"])
            except DataNotReady as exc:
                print(f"{cfg['rule']}: data not ready ({exc})", file=sys.stderr)
                failures += 1
                continue
            print(cfg["rule"], json.dumps({k: status.get(k) for k in ("state", "asof", "last_decision", "nav", "benchmark_nav", "excess_return")}))
            if args.execute and cfg.get("allocation_pct", 0) > 0:
                print(f"  {cfg['rule']}: shadow only, no order placement is implemented for this rule", file=sys.stderr)
            continue
        try:
            status = run_rule(cfg, session, membership, fetch_closes, PAPER_DIR / cfg["rule"])
        except DataNotReady as exc:
            print(f"{cfg['rule']}: data not ready ({exc})", file=sys.stderr)
            failures += 1
            continue
        line = {k: status.get(k) for k in ("state", "asof", "last_decision", "nav", "benchmark_nav", "excess_return")}
        print(cfg["rule"], json.dumps(line))
        if status.get("decisions_changed_since_recorded"):
            print(f"  WARNING: recomputed picks differ from the recorded decisions: {status['decisions_changed_since_recorded']}", file=sys.stderr)
        if args.execute and "stock" in kinds and status["state"] == "running" and cfg.get("allocation_pct", 0) > 0 \
                and status["last_decision"] == str(session.date()):
            prices = fetch_closes(status["holdings"], session - pd.Timedelta(days=10), session).iloc[-1].to_dict()
            result = execute_orders(cfg, status, prices, hypothesis_id(cfg["rule"]))
            for order in result["orders"]:
                print("  order", json.dumps(order))
            for key in ("skipped", "unpriced"):
                if result.get(key):
                    print(f"  {key}: {result[key]}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
