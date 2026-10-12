"""The only way this project talks to Alpaca's trading API: paper accounts only.

Guards, in order:
  1. TradingClient is always built with paper=True and no url_override.
  2. The resulting base URL must be Alpaca's paper endpoint.
  3. On connect, the account number must carry the paper prefix "PA".
Any failure raises LiveAccountError and no client is returned.
"""

from alpaca.common.enums import BaseURL
from alpaca.trading.client import TradingClient

from core.config import PaperKeys, load_paper_keys

PAPER_URL = BaseURL.TRADING_PAPER.value
PAPER_ACCOUNT_PREFIX = "PA"


class LiveAccountError(RuntimeError):
    pass


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
