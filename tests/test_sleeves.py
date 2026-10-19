import json
from types import SimpleNamespace

import pandas as pd
import pytest

from core import paper_runner as pr
from core import sleeves, snapshot_orders as so
from core.market_calendar import trading_days
from core.risk import ConfigError, load_risk_limits


class FakeAccount:
    """Just enough of the paper client: orders placed through core.broker.submit_order land in `orders` as filled."""

    def __init__(self, monkeypatch, equity=100_000.0):
        self.orders, self.sent = [], []
        self.client = SimpleNamespace(
            get_account=lambda: SimpleNamespace(equity=str(equity), last_equity=str(equity)),
            get_all_positions=lambda: [],
            get_orders=lambda request: list(self.orders))

        def submit(client, order, reasoning, strategy, **kw):
            self.sent.append((order, kw))
            self.orders.append(self.order(kw["client_order_id"], order.symbol, order.side, order.qty))

        monkeypatch.setattr("core.broker.submit_order", submit)

    @staticmethod
    def order(cid, symbol, side, qty, status="filled", filled=None):
        return SimpleNamespace(client_order_id=cid, symbol=symbol, side=side, status=status,
                               filled_qty=str(qty if filled is None else filled), submitted_at=pd.Timestamp("2026-10-15", tz="UTC"))


def test_sleeve_is_rebuilt_from_the_rules_own_filled_orders():
    orders = [FakeAccount.order("ruleA__2026-10-15__AAA__buy", "AAA", "buy", 10),
              FakeAccount.order("ruleA__2026-10-19__AAA__sell", "AAA", "sell", 4),
              FakeAccount.order("ruleA__2026-10-19__BBB__buy", "BBB", "buy", 7, status="partially_filled", filled=3),
              FakeAccount.order("ruleA__2026-10-19__CCC__buy", "CCC", "buy", 5, status="canceled", filled=0)]
    assert sleeves.sleeve_shares(orders) == {"AAA": 6.0, "BBB": 3.0}
    assert [o.symbol for o in sleeves.open_orders(orders)] == ["BBB"]


def test_rule_orders_ignore_other_rules_and_untagged_orders(monkeypatch):
    account = FakeAccount(monkeypatch)
    account.orders = [account.order("ruleA__d__AAA__buy", "AAA", "buy", 1), account.order("ruleAB__d__AAA__buy", "AAA", "buy", 9),
                      account.order(None, "AAA", "buy", 99)]
    assert [o.client_order_id for o in sleeves.rule_orders(account.client, "ruleA")] == ["ruleA__d__AAA__buy"]


def test_two_rules_on_the_same_stock_stay_separate(monkeypatch):
    account = FakeAccount(monkeypatch)
    account.orders = [account.order("momentum__2026-09-30__AAA__buy", "AAA", "buy", 10)]
    out = pr.place_sleeve_orders("reversal", ["AAA"], {"AAA": 100.0}, 5.0, "2026-10-15", lambda o: "test", client=account.client)
    assert [(o["symbol"], o["side"], o["qty"]) for o in out["orders"]] == [("AAA", "buy", 50)]      # 5% of 100k, none of momentum's shares
    assert account.sent[0][1]["client_order_id"] == "reversal__2026-10-15__AAA__buy"
    # next decision drops AAA: the reversal sleeve sells its own 50, momentum keeps its 10
    out = pr.place_sleeve_orders("reversal", [], {"AAA": 100.0}, 5.0, "2026-10-19", lambda o: "test", client=account.client)
    assert [(o["side"], o["qty"]) for o in out["orders"]] == [("sell", 50)]
    assert sleeves.sleeve_shares(sleeves.rule_orders(account.client, "momentum")) == {"AAA": 10.0}


def test_open_orders_stop_a_second_rebalance_and_missing_prices_are_reported(monkeypatch):
    account = FakeAccount(monkeypatch)
    account.orders = [account.order("r__d__AAA__buy", "AAA", "buy", 5, status="new", filled=0)]
    out = pr.place_sleeve_orders("r", ["AAA"], {"AAA": 10.0}, 5.0, "d2", lambda o: "t", client=account.client)
    assert out["orders"] == [] and "still open" in out["skipped"] and account.sent == []
    account = FakeAccount(monkeypatch)
    out = pr.place_sleeve_orders("r", ["AAA", "ZZZ"], {"AAA": 10.0}, 5.0, "d", lambda o: "t", client=account.client)
    assert out["unpriced"] == ["ZZZ"] and [o["symbol"] for o in out["orders"]] == ["AAA"]


def test_stop_check_leaves_late_orders_unsent(monkeypatch):
    account = FakeAccount(monkeypatch)
    out = pr.place_sleeve_orders("r", ["AAA", "BBB"], {"AAA": 10.0, "BBB": 10.0}, 5.0, "d", lambda o: "t",
                                 client=account.client, stop_check=lambda: len(account.sent) >= 1)
    assert [o["result"] for o in out["orders"]] == ["submitted", "late"] and len(account.sent) == 1


def test_signal_rule_orders_follow_the_position(monkeypatch):
    cfg = {"rule": "xlk", "symbol": "XLK", "allocation_pct": 5}
    account = FakeAccount(monkeypatch)
    monkeypatch.setattr("core.broker.get_paper_client", lambda: account.client)
    day = pd.Timestamp("2026-10-20")
    out = pr.execute_signal_orders(cfg, {"in_position": True}, 250.0, day)
    assert [(o["side"], o["qty"]) for o in out["orders"]] == [("buy", 20)]
    assert pr.execute_signal_orders(cfg, {"in_position": True}, 250.0, day + pd.Timedelta(days=1))["orders"] == []   # already there
    out = pr.execute_signal_orders(cfg, {"in_position": False}, 255.0, day + pd.Timedelta(days=2))
    assert [(o["side"], o["qty"]) for o in out["orders"]] == [("sell", 20)]


def test_risk_limits_allow_leverage_up_to_the_account_margin(tmp_path):
    path = tmp_path / "r.yaml"
    base = "max_position_pct: 5\nmax_open_positions: 250\nmax_order_notional: 5000\nmax_daily_loss_pct: 2\nallow_short: false\n"
    path.write_text(base + "max_gross_exposure_pct: 150\n")
    assert load_risk_limits(path).max_gross_exposure_pct == 150
    path.write_text(base + "max_gross_exposure_pct: 250\n")
    with pytest.raises(ConfigError):
        load_risk_limits(path)
    limits = load_risk_limits()                                    # the tracked file
    allocations = sum(c["allocation_pct"] for c in pr.load_tracked())
    assert allocations <= limits.max_gross_exposure_pct
    assert all(c["allocation_pct"] <= limits.max_position_pct for c in pr.load_tracked() if c.get("kind") == "signal")


# --- the 15:45 market-on-close run ------------------------------------------------------------

TODAY = pd.Timestamp("2026-10-21")                                 # a decision session of a rev5 two-session rule started 2026-10-15
TICKERS = [f"T{i:02d}" for i in range(20)]
CFG = {"rule": "stock_rev5_h2_band", "kind": "snapshot", "strategy_rule": "rev5_h2_band_s", "start": "2026-10-15",
       "initial_cash": 100000, "allocation_pct": 25}


class Clock:
    def __init__(self, at="2026-10-21 15:40"):
        self.now = pd.Timestamp(at, tz="America/New_York")
        self.slept = []

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.slept.append(seconds)
        self.now += pd.Timedelta(seconds=seconds)


@pytest.fixture
def env(monkeypatch, tmp_path):
    skips = []
    monkeypatch.setattr(so.journal, "record", lambda action, reasoning, strategy, **kw: skips.append((action, reasoning)))
    index = trading_days("2026-10-01", "2026-10-20")
    closes = pd.DataFrame(100.0, index, TICKERS)
    snap = pd.Series({t: 100.0 - i for i, t in enumerate(TICKERS)})          # T19 fell the most
    membership = pd.Series([frozenset(TICKERS)], index=[pd.Timestamp("2026-01-01")])
    return SimpleNamespace(account=FakeAccount(monkeypatch), clock=Clock(), closes=closes, snap=snap, membership=membership,
                           out=tmp_path, skips=skips)


def go(env, execute, snap=None, **kw):
    snap = env.snap if snap is None else snap
    return so.run(execute, now_fn=env.clock, sleep_fn=env.clock.sleep, fetch_closes_fn=lambda *a, **k: env.closes,
                  snapshot_fn=lambda symbols, day: snap, membership=env.membership, client=env.account.client,
                  out_root=env.out, tracked=[CFG], **kw)


def test_dry_run_sends_and_writes_nothing(env, capsys):
    assert go(env, execute=False) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["dry_run"] and report["picks_list"] == ["T18", "T19"]
    assert env.account.sent == [] and not list(env.out.rglob("*.json"))


def test_execute_waits_for_the_bar_writes_the_decision_and_sends_close_orders(env):
    assert go(env, execute=True) == 0
    assert env.clock.slept and env.clock.now.time() >= so.SNAPSHOT_READY
    decision = json.loads((env.out / CFG["rule"] / "decisions" / "2026-10-21.json").read_text())
    assert decision["picks"] == ["T18", "T19"] and decision["snapshot_1545"]["T19"] == 81.0
    assert sorted(o.symbol for o, _ in env.account.sent) == ["T18", "T19"]
    for order, kw in env.account.sent:
        assert str(kw["time_in_force"].value) == "cls" and kw["client_order_id"].startswith("stock_rev5_h2_band__2026-10-21__")
        assert order.qty == int(12_500 // 82) or order.qty == int(12_500 // 81)      # 25% of equity over two names
    # running it again changes nothing: stored decision, sleeve already at target
    sent = len(env.account.sent)
    assert go(env, execute=True) == 0 and len(env.account.sent) == sent


def test_previous_picks_are_held_inside_the_band(env):
    previous = env.out / CFG["rule"] / "decisions"
    previous.mkdir(parents=True)
    (previous / "2026-10-19.json").write_text(json.dumps({"picks": ["T17"]}))
    snap = env.snap.copy()
    snap["T17"] = 80.0                                             # rank 2 of 20: inside the top 30%, so it is kept
    go(env, execute=False)
    assert go(env, execute=True, snap=snap) == 0
    assert json.loads((previous / "2026-10-21.json").read_text())["picks"] == ["T17", "T19"]


def test_start_after_the_close_order_cutoff_falls_back_to_plain_market_orders(env, capsys):
    env.clock.now = pd.Timestamp("2026-10-21 15:50", tz="America/New_York")
    assert go(env, execute=True) == 0
    assert sorted(o.symbol for o, _ in env.account.sent) == ["T18", "T19"]
    assert all(str(kw["time_in_force"].value) == "day" for _, kw in env.account.sent)
    assert json.loads(capsys.readouterr().out)["sent_as_plain_market_orders"] == 2


def test_start_too_close_to_the_close_sends_nothing_and_leaves_it_to_the_catch_up(env):
    env.clock.now = pd.Timestamp("2026-10-21 15:59", tz="America/New_York")
    assert go(env, execute=True) == 2
    assert env.account.sent == [] and "catch-up" in env.skips[0][1]


def test_sparse_snapshot_sends_nothing(env):
    assert go(env, execute=True, snap=env.snap.iloc[:10]) == 2
    assert env.account.sent == [] and "only 10 of 20" in env.skips[0][1]
    assert env.clock.now.time() >= so.RETRY_UNTIL                 # it kept asking until the deadline


def test_snapshot_published_late_is_waited_for(env):
    calls = []

    def snapshot(symbols, day):
        calls.append(env.clock.now)
        return env.snap.iloc[:0] if len(calls) < 4 else env.snap

    so_run = so.run(True, now_fn=env.clock, sleep_fn=env.clock.sleep, fetch_closes_fn=lambda *a, **k: env.closes,
                    snapshot_fn=snapshot, membership=env.membership, client=env.account.client, out_root=env.out, tracked=[CFG])
    assert so_run == 0 and len(calls) == 4 and sorted(o.symbol for o, _ in env.account.sent) == ["T18", "T19"]


def test_not_a_decision_day(env):
    env.clock.now = pd.Timestamp("2026-10-20 15:40", tz="America/New_York")
    assert go(env, execute=True) == 0 and env.account.sent == []


def test_early_close_days():
    assert so.early_close(pd.Timestamp("2026-11-27")) and so.early_close(pd.Timestamp("2026-12-24"))
    assert not so.early_close(pd.Timestamp("2026-10-21")) and not so.early_close(pd.Timestamp("2026-11-26"))


# --- catch-up of a missed decision ---------------------------------------------------------------

def catch(env, execute=True, hour="09:35", day="2026-10-22", history=None):
    env.clock.now = pd.Timestamp(f"{day} {hour}", tz="America/New_York")
    closes = pd.DataFrame(100.0, trading_days("2026-10-01", "2026-10-21"), TICKERS)
    return so.catch_up(execute, now_fn=env.clock, fetch_closes_fn=lambda *a, **k: closes,
                       history_snapshot_fn=history or (lambda symbols, day: env.snap), membership=env.membership,
                       client=env.account.client, out_root=env.out, tracked=[CFG])


def test_catch_up_places_a_missed_decision_at_the_next_open(env, capsys):
    assert catch(env) == 0                                         # 2026-10-21 was a decision session and nothing was sent
    assert sorted(o.symbol for o, _ in env.account.sent) == ["T18", "T19"]
    assert all(str(kw["time_in_force"].value) == "day" and "__2026-10-21__" in kw["client_order_id"] for _, kw in env.account.sent)
    assert json.loads((env.out / CFG["rule"] / "decisions" / "2026-10-21.json").read_text())["feed"] == "history, catch-up"
    sent = len(env.account.sent)
    assert catch(env) == 0 and len(env.account.sent) == sent       # a second run finds the orders and does nothing
    assert "not needed" in capsys.readouterr().out


def test_catch_up_uses_the_stored_decision_and_ignores_other_days(env):
    decisions = env.out / CFG["rule"] / "decisions"
    decisions.mkdir(parents=True)
    (decisions / "2026-10-21.json").write_text(json.dumps({"picks": ["T01"], "snapshot_1545": {"T01": 50.0}}))
    assert catch(env) == 0 and [o.symbol for o, _ in env.account.sent] == ["T01"]
    env2 = env.account.sent.copy()
    assert catch(env, day="2026-10-23") == 0 and env.account.sent == env2    # 10-22 was not a decision session


def test_catch_up_does_nothing_when_the_orders_went_out(env):
    assert go(env, execute=True) == 0
    sent = len(env.account.sent)
    assert catch(env) == 0 and len(env.account.sent) == sent
