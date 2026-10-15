"""The only way this project talks to Alpaca's trading API: paper accounts only.

Guards, in order:
  1. TradingClient is always built with paper=True and no url_override.
  2. The resulting base URL must be Alpaca's paper endpoint.
  3. On connect, the account number must carry the paper prefix "PA".
Any failure raises LiveAccountError and no client is returned.

Orders go through submit_order(), which re-checks the endpoint, runs the risk
check, and journals the decision whether or not the order is sent.
"""

from pathlib import Path

from alpaca.common.enums import BaseURL
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import MarketOrderRequest

from core import journal
from core.config import PaperKeys, load_paper_keys
from core.risk import AccountState, ProposedOrder, RiskLimits, check_order, load_risk_limits

PAPER_URL = BaseURL.TRADING_PAPER.value
PAPER_ACCOUNT_PREFIX = "PA"


class LiveAccountError(RuntimeError):
    pass


class RiskViolation(RuntimeError):
    def __init__(self, violations: list[str]):
        super().__init__("; ".join(violations))
        self.violations = violations


def _check_paper_url(client: TradingClient) -> None:
    base_url = str(getattr(client._base_url, "value", client._base_url))
    if base_url.rstrip("/") != PAPER_URL:
        raise LiveAccountError(f"refusing non-paper endpoint: {base_url}")


def get_paper_client(keys: PaperKeys | None = None, verify_account: bool = True) -> TradingClient:
    keys = keys or load_paper_keys()
    client = TradingClient(keys.api_key, keys.secret_key, paper=True)
    _check_paper_url(client)
    if verify_account:
        account = client.get_account()
        if not str(account.account_number).startswith(PAPER_ACCOUNT_PREFIX):
            raise LiveAccountError("connected account is not a paper account; refusing to continue")
    return client


def account_state(client: TradingClient) -> AccountState:
    account = client.get_account()
    positions = {p.symbol: float(p.market_value) for p in client.get_all_positions()}
    return AccountState(float(account.equity), float(account.last_equity), positions)


def submit_order(client: TradingClient, order: ProposedOrder, reasoning: str, strategy: str, *,
                 hypothesis_id: int | None = None, limits: RiskLimits | None = None,
                 journal_dir: Path = journal.JOURNAL_DIR, time_in_force: TimeInForce = TimeInForce.DAY,
                 client_order_id: str | None = None):
    """Risk-check, journal, and send a market order. Raises RiskViolation if blocked.

    time_in_force=TimeInForce.CLS makes it a market-on-close order (Alpaca's cut-off is 15:50 New York).
    client_order_id tags the order with the rule that placed it (see core.sleeves)."""
    _check_paper_url(client)
    limits = limits or load_risk_limits()
    common = dict(strategy=strategy, symbol=order.symbol, side=order.side, qty=order.qty,
                  price=order.price, hypothesis_id=hypothesis_id, journal_dir=journal_dir)

    violations = check_order(order, account_state(client), limits)
    if violations:
        journal.record("blocked", reasoning, risk_violations=violations, **common)
        raise RiskViolation(violations)

    request = MarketOrderRequest(symbol=order.symbol, qty=order.qty, side=OrderSide(order.side),
                                 time_in_force=time_in_force, client_order_id=client_order_id)
    try:
        placed = client.submit_order(request)
    except Exception as exc:
        journal.record("error", reasoning, extra={"error": f"{type(exc).__name__}: {exc}"}, **common)
        raise
    journal.record("submitted", reasoning, order_id=str(placed.id), **common)
    return placed
