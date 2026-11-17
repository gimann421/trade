"""Read-only portfolio import: CSV/manual holdings, plus the guard for a future Schwab read-only connection.

The owner's real account is at Schwab. Until read-only API access exists (developer-app approval and OAuth
must be done by the owner), a holdings CSV the owner exports and confirms is the supported path. NEXUS never
sends anything to the real account: ``assert_schwab_read_only`` refuses every non-GET method and every path
outside account/position reads.
"""
from __future__ import annotations

import csv
import io
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit

from .accounting import import_actual_snapshot
from .domain.enums import AssetClass, CapabilityTier
from .domain.models import Instrument
from .errors import LaunchBoundaryViolation, NexusError
from .store import Store

CASH_LABELS = {"cash", "cash & cash investments", "cash and cash investments", "cash & money market", "account total cash"}
SYMBOL_COLS = ("symbol", "ticker")
QTY_COLS = ("quantity", "qty", "shares")
BASIS_COLS = ("cost basis", "cost_basis", "costbasis", "cost basis total")
VALUE_COLS = ("market value", "value", "amount")
_SYM = re.compile(r"^[A-Z][A-Z0-9.\-]{0,9}$")


def _num(raw: str) -> Decimal | None:
    s = (raw or "").strip().replace("$", "").replace(",", "")
    if s in ("", "--", "N/A", "n/a"):
        return None
    neg = s.startswith("(") and s.endswith(")")
    try:
        d = Decimal(s.strip("()"))
    except InvalidOperation:
        raise NexusError(f"unparseable number {raw!r}") from None
    return -d if neg else d


def _col(header: list[str], names: tuple[str, ...]) -> int | None:
    h = [x.strip().lower() for x in header]
    for n in names:
        if n in h:
            return h.index(n)
    return None


def parse_holdings_csv(text: str) -> tuple[dict[str, str], dict[str, dict], list[str]]:
    """Return (cash, holdings, estimated_fields). Strict: anything ambiguous raises."""
    rows = list(csv.reader(io.StringIO(text)))
    rows = [r for r in rows if any(c.strip() for c in r)]
    if not rows:
        raise NexusError("empty holdings file")
    header = rows[0]
    si, qi = _col(header, SYMBOL_COLS), _col(header, QTY_COLS)
    bi, vi = _col(header, BASIS_COLS), _col(header, VALUE_COLS)
    if si is None:
        raise NexusError("no Symbol column found")
    cash, holdings, estimated = Decimal(0), {}, []
    seen_cash = False
    for r in rows[1:]:
        sym = r[si].strip()
        if sym.lower() in CASH_LABELS:
            v = _num(r[vi]) if vi is not None and vi < len(r) else None
            if v is None:
                raise NexusError("cash row has no value")
            cash += v
            seen_cash = True
            continue
        if sym.lower().startswith(("account total", "total", "positions total")):
            continue
        sym = sym.upper()
        if not _SYM.match(sym):
            raise NexusError(f"unrecognized symbol {sym!r}")
        if qi is None or qi >= len(r):
            raise NexusError("no Quantity column found")
        q = _num(r[qi])
        if q is None or q == 0:
            raise NexusError(f"{sym}: missing quantity")
        if q < 0:
            raise NexusError(f"{sym}: short/negative positions are not supported yet")
        if sym in holdings:
            raise NexusError(f"{sym}: duplicate row")
        basis = _num(r[bi]) if bi is not None and bi < len(r) else None
        if basis is None:
            estimated.append(f"{sym}.cost_basis")
        holdings[sym] = {"quantity": str(q), "cost_basis": None if basis is None else str(basis)}
    if not seen_cash:
        estimated.append("cash")
    return {"USD": str(cash)}, holdings, estimated


def import_holdings_csv(store: Store, account_id: str, text: str, as_of: datetime, source: str, confirmed_by: str,
                        auto_register: bool = True) -> str:
    """Parse the owner's CSV and record an immutable, owner-confirmed ACTUAL snapshot."""
    cash, holdings, estimated = parse_holdings_csv(text)
    mapped: dict[str, dict] = {}
    for sym, h in holdings.items():
        iid = f"EQ:US:{sym}"
        if store.get_instrument(iid) is None:
            if not auto_register:
                raise NexusError(f"{sym} is not in the instrument registry")
            store.register_instrument(Instrument(iid, {"owner_csv": sym}, AssetClass.EQUITY, "USD", "America/New_York",
                                                 capability_tier=CapabilityTier.R1,
                                                 known_failure_modes=("registered from owner CSV; venue and asset subclass unverified",)))
            estimated.append(f"{sym}.instrument_details")
        mapped[iid] = h
    return import_actual_snapshot(store, account_id, as_of, source, confirmed_by, cash=cash, holdings=mapped,
                                  estimated_fields=estimated)


# ---- Schwab read-only boundary (no vendor response shapes are assumed here) ----
SCHWAB_HOST = "api.schwabapi.com"
_SCHWAB_READ_PATHS = re.compile(r"^/trader/v1/accounts(/[0-9A-Za-z]+)?(/positions)?/?$")


def assert_schwab_read_only(method: str, url: str) -> None:
    """Only GET of the accounts/positions read endpoints on Schwab's API host. Orders and everything else are refused."""
    u = urlsplit(url)
    if method.upper() != "GET":
        raise LaunchBoundaryViolation("Schwab access is read-only: only GET is permitted")
    if not (u.scheme == "https" and u.hostname == SCHWAB_HOST and u.username is None and u.port is None):
        raise LaunchBoundaryViolation("only https://api.schwabapi.com may be contacted")
    if "order" in u.path.lower() or not _SCHWAB_READ_PATHS.match(u.path):
        raise LaunchBoundaryViolation("Schwab path not in the read-only allowlist (orders are never permitted)")
