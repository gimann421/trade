"""Per-rule sleeves inside the one shared paper account.

Alpaca nets every order into one position per symbol, so two rules holding the same stock cannot be
told apart from the account's positions. Instead every order carries a client_order_id that starts with
the rule id, and a rule's sleeve is rebuilt from the filled quantities of its own orders. The rule only
ever buys and sells its own shares, and its dollar budget is a fixed share of account equity
(allocation_pct in paper/tracked.json).

client_order_id = <rule>__<decision date>__<SYMBOL>__<side>. Alpaca rejects a repeated id, so running
the same rebalance twice cannot double the orders.
"""

from datetime import timezone

import pandas as pd
from alpaca.common.enums import Sort

SEP = "__"
OPEN_STATES = {"new", "partially_filled", "accepted", "pending_new", "accepted_for_bidding", "held",
               "pending_cancel", "pending_replace", "pending_review"}


def order_tag(rule: str, decision_date, symbol: str, side: str) -> str:
    return SEP.join((rule, str(decision_date), symbol, side))


def _status(order) -> str:
    return str(getattr(order.status, "value", order.status)).lower()


def _side(order) -> str:
    return str(getattr(order.side, "value", order.side)).lower()


def rule_orders(client, rule: str, since="2026-01-01") -> list:
    """Every order of this rule (any state), oldest first, found by the rule prefix of client_order_id."""
    from alpaca.trading.enums import QueryOrderStatus
    from alpaca.trading.requests import GetOrdersRequest

    found, after = [], pd.Timestamp(since, tz="UTC").to_pydatetime()
    while True:
        batch = client.get_orders(GetOrdersRequest(status=QueryOrderStatus.ALL, limit=500, after=after, direction=Sort.ASC))
        if not batch:
            break
        found += [o for o in batch if str(o.client_order_id or "").startswith(rule + SEP)]
        last = max(pd.Timestamp(o.submitted_at) for o in batch)
        if len(batch) < 500:
            break
        after = last.tz_convert(timezone.utc).to_pydatetime() if last.tzinfo else last.to_pydatetime()
    return found


def sleeve_shares(orders) -> dict[str, float]:
    """Shares the rule holds now: filled buys minus filled sells, zero positions dropped."""
    shares: dict[str, float] = {}
    for o in orders:
        filled = float(o.filled_qty or 0)
        if filled:
            shares[o.symbol] = shares.get(o.symbol, 0.0) + (filled if _side(o) == "buy" else -filled)
    return {s: q for s, q in sorted(shares.items()) if abs(q) > 1e-9}


def open_orders(orders) -> list:
    return [o for o in orders if _status(o) in OPEN_STATES]
