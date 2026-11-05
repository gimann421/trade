"""Emergency stop / pause. State is derived from the immutable event log (auditable, restart-safe)."""
from __future__ import annotations

from .audit import EventStore
from .domain.enums import EventType
from .errors import SystemHalted


class Controls:
    def __init__(self, events: EventStore):
        self.events = events

    def _last(self):
        row = self.events.conn.execute(
            "SELECT event_type, payload_json FROM events WHERE event_type IN (?, ?) ORDER BY seq DESC LIMIT 1",
            (EventType.CONTROL_HALT.value, EventType.CONTROL_RESUME.value)).fetchone()
        return row

    def is_halted(self) -> bool:
        row = self._last()
        return bool(row and row["event_type"] == EventType.CONTROL_HALT.value)

    def halt(self, actor: str, reason: str):
        return self.events.append(EventType.CONTROL_HALT, "controls", actor, {"reason": reason})

    def resume(self, actor: str, reason: str):
        return self.events.append(EventType.CONTROL_RESUME, "controls", actor, {"reason": reason})

    def assert_can_create_simulated_orders(self) -> None:
        """Gate every new simulated order/recommendation on this (fails closed)."""
        if self.is_halted():
            raise SystemHalted("emergency stop is active: new simulated orders are blocked")
        self.events.verify_chain()  # a broken audit chain also blocks
