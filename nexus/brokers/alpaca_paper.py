"""Alpaca PAPER order adapter. The only write-capable broker code in NEXUS, and it can only reach the paper API.

Every request URL passes ``assert_paper_endpoint``; credentials come only via ``paper_credentials`` (env, gated on the
owner-authorized ``paper_broker_order`` capability); every submission needs an approved, pre-registered NEXUS order
whose account is a PAPER_SLEEVE. Nothing here can address the live host, move money or touch the real account.
"""
from __future__ import annotations

import json
import urllib.request
from datetime import datetime
from typing import Callable

from .. import permissions
from ..domain.enums import EventType, OrderState
from ..errors import LaunchBoundaryViolation, NexusError
from ..orders import current_state, transition
from ..paper_guard import PAPER_ENDPOINT, assert_paper_endpoint, paper_credentials
from ..secrets import Secret
from ..store import Store

Transport = Callable[[str, str, dict[str, str], dict | None], dict]   # (method, url, headers, json_body) -> parsed JSON
ALLOWED = {("POST", "/v2/orders"), ("GET", "/v2/orders"), ("DELETE", "/v2/orders"), ("GET", "/v2/account")}


def urllib_transport(method: str, url: str, headers: dict[str, str], body: dict | None) -> dict:
    assert_paper_endpoint(url)
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers={**headers, "content-type": "application/json"}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 (host asserted above)
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except Exception as exc:
        raise NexusError(f"alpaca paper request failed: {type(exc).__name__}") from None


class AlpacaPaperBroker:
    def __init__(self, store: Store, key_id: Secret, secret: Secret, transport: Transport = urllib_transport):
        permissions.require(permissions.Capability.PAPER_BROKER_ORDER, store.config.permissions.allowed)
        self.store, self._k, self._s, self._send = store, key_id, secret, transport

    @classmethod
    def from_env(cls, store: Store, environ: dict[str, str] | None = None, **kw) -> "AlpacaPaperBroker":
        k, s = paper_credentials(store.config.permissions.allowed, environ)
        return cls(store, k, s, **kw)

    def _call(self, method: str, path: str, body: dict | None = None, query: str = "") -> dict:
        base = "/" + "/".join(path.strip("/").split("/")[:2])
        if (method, base) not in ALLOWED:
            raise LaunchBoundaryViolation(f"{method} {path} is not an allowed paper-broker call")
        url = f"{PAPER_ENDPOINT}{path}{query}"
        assert_paper_endpoint(url)
        headers = {"APCA-API-KEY-ID": self._k.reveal(), "APCA-API-SECRET-KEY": self._s.reveal()}
        return self._send(method, url, headers, body)

    def submit(self, order_id: str, now: datetime) -> str:
        """Send an approved NEXUS order to the paper API. Idempotent via client_order_id = NEXUS order id."""
        self.store.controls.assert_can_create_simulated_orders()
        o = self.store.conn.execute("SELECT * FROM orders WHERE order_id=?", (order_id,)).fetchone()
        if o is None:
            raise NexusError("unknown order")
        if o["mode"] != "paper_broker":
            raise NexusError("only orders created with mode='paper_broker' may be sent to the paper broker")
        if current_state(self.store, order_id) is not OrderState.ACCEPTED_BY_SIMULATOR:
            raise NexusError("only risk-approved orders (ACCEPTED_BY_SIMULATOR) may be submitted")
        kind = self.store.conn.execute("SELECT kind FROM ledger_accounts WHERE account_id=?", (o["account_id"],)).fetchone()["kind"]
        if kind != "PAPER_SLEEVE":
            raise LaunchBoundaryViolation("paper broker orders may only come from PAPER_SLEEVE accounts")
        sym = (self.store.get_instrument(o["instrument_id"]).symbols.get("alpaca")
               or o["instrument_id"].rsplit(":", 1)[-1])
        body = {"symbol": sym, "qty": o["quantity"], "side": o["side"].lower(), "type": o["order_type"].lower(),
                "time_in_force": "day", "client_order_id": order_id}
        if o["limit_price"]:
            body["limit_price"] = o["limit_price"]
        resp = self._call("POST", "/v2/orders", body)
        broker_id = resp.get("id")
        if not broker_id:
            raise NexusError("paper broker response had no order id; leaving order unfilled")
        self.store.events.append(EventType.ORDER_STATE_CHANGED,
                                 "alpaca_paper", "system", {"order_id": order_id, "broker_order_id": broker_id, "note": "submitted to PAPER API"},
                                 occurred_at=now)
        return broker_id
