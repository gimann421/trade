"""Load and validate config/risk_limits.yaml, and check proposed orders against it."""

from dataclasses import dataclass, fields
from pathlib import Path

import yaml

from core.config import ROOT, ConfigError

RISK_PATH = ROOT / "config" / "risk_limits.yaml"


@dataclass(frozen=True)
class RiskLimits:
    max_position_pct: float
    max_gross_exposure_pct: float
    max_open_positions: int
    max_order_notional: float
    max_daily_loss_pct: float
    allow_short: bool


def load_risk_limits(path: Path = RISK_PATH) -> RiskLimits:
    raw = yaml.safe_load(path.read_text()) or {}
    expected = {f.name for f in fields(RiskLimits)}
    missing, unknown = expected - raw.keys(), raw.keys() - expected
    if missing or unknown:
        raise ConfigError(f"{path.name}: missing={sorted(missing)} unknown={sorted(unknown)}")
    limits = RiskLimits(**raw)
    for name in ("max_position_pct", "max_gross_exposure_pct", "max_daily_loss_pct"):
        if not 0 < getattr(limits, name) <= 100:
            raise ConfigError(f"{name} must be in (0, 100]")
    if limits.max_open_positions < 1 or limits.max_order_notional <= 0:
        raise ConfigError("max_open_positions and max_order_notional must be positive")
    return limits


@dataclass(frozen=True)
class AccountState:
    equity: float
    day_start_equity: float           # Alpaca's last_equity: equity at the previous close
    positions: dict[str, float]       # symbol -> signed market value (negative = short)


@dataclass(frozen=True)
class ProposedOrder:
    symbol: str
    side: str                         # "buy" or "sell"
    qty: float
    price: float                      # estimated fill price, used to size the order

    @property
    def notional(self) -> float:
        return self.qty * self.price

    @property
    def signed_notional(self) -> float:
        return self.notional if self.side == "buy" else -self.notional


def check_order(order: ProposedOrder, state: AccountState, limits: RiskLimits) -> list[str]:
    """Return every limit the order would break; an empty list means it may go.

    Orders that only shrink an existing position are always allowed (apart from
    the short rule), so the limits never trap you in a losing position.
    """
    if order.side not in ("buy", "sell"):
        return [f"side must be 'buy' or 'sell', got {order.side!r}"]
    if order.qty <= 0 or order.price <= 0:
        return ["qty and price must be positive"]
    if state.equity <= 0:
        return ["account equity is not positive"]

    violations = []
    current = state.positions.get(order.symbol, 0.0)
    new = current + order.signed_notional
    reducing = abs(new) < abs(current) and new * current >= 0

    if new < 0 and not limits.allow_short:
        violations.append(f"would leave {order.symbol} short (${new:,.0f}); shorting is disabled")
    if reducing:
        return violations

    if order.notional > limits.max_order_notional:
        violations.append(f"order ${order.notional:,.0f} exceeds max_order_notional ${limits.max_order_notional:,.0f}")

    position_cap = state.equity * limits.max_position_pct / 100
    if abs(new) > position_cap:
        violations.append(f"{order.symbol} position ${abs(new):,.0f} would exceed "
                          f"{limits.max_position_pct}% of equity (${position_cap:,.0f})")

    gross = sum(abs(v) for v in state.positions.values()) - abs(current) + abs(new)
    gross_cap = state.equity * limits.max_gross_exposure_pct / 100
    if gross > gross_cap:
        violations.append(f"gross exposure ${gross:,.0f} would exceed "
                          f"{limits.max_gross_exposure_pct}% of equity (${gross_cap:,.0f})")

    open_positions = sum(1 for v in state.positions.values() if v != 0)
    if current == 0 and open_positions >= limits.max_open_positions:
        violations.append(f"already at max_open_positions ({limits.max_open_positions})")

    if state.day_start_equity > 0:
        day_pnl_pct = (state.equity - state.day_start_equity) / state.day_start_equity * 100
        if day_pnl_pct <= -limits.max_daily_loss_pct:
            violations.append(f"down {-day_pnl_pct:.2f}% today, past max_daily_loss_pct "
                              f"{limits.max_daily_loss_pct}%; only risk-reducing orders allowed")
    return violations
