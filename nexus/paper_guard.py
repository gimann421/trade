"""Paper-only broker boundary. The ONLY broker endpoint NEXUS may ever address is Alpaca's paper API.

Order adapters (Milestone 4) must call ``assert_paper_endpoint`` on every request URL and obtain
credentials only through ``paper_credentials``. Anything else - the live host, a lookalike host,
plain http, embedded credentials, a custom port - is refused.
"""
from __future__ import annotations

from urllib.parse import urlsplit

from . import permissions
from .errors import LaunchBoundaryViolation
from .secrets import Secret, get_secret

PAPER_ENDPOINT = "https://paper-api.alpaca.markets"
KEY_ID_ENV = "NEXUS_ALPACA_PAPER_KEY_ID"
SECRET_ENV = "NEXUS_ALPACA_PAPER_SECRET_KEY"


def assert_paper_endpoint(url: str) -> None:
    u = urlsplit(url)
    ok = (u.scheme == "https" and u.hostname == "paper-api.alpaca.markets"
          and u.username is None and u.password is None and u.port is None)
    if not ok:
        raise LaunchBoundaryViolation("only the Alpaca paper endpoint is permitted; live endpoints are refused")


def paper_credentials(narrowed_to, environ: dict[str, str] | None = None) -> tuple[Secret, Secret]:
    permissions.require(permissions.Capability.PAPER_BROKER_ORDER, narrowed_to)
    return get_secret(KEY_ID_ENV, environ), get_secret(SECRET_ENV, environ)
