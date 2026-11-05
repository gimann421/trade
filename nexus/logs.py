"""Structured JSON logging with mandatory secret redaction."""
from __future__ import annotations

import json
import logging

from .secrets import redact
from .timeutil import to_iso, utcnow


class RedactingJsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": to_iso(utcnow()),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        extra = getattr(record, "fields", None)
        if isinstance(extra, dict):
            payload["fields"] = extra
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return redact(json.dumps(payload, default=str, sort_keys=True))


def get_logger(name: str = "nexus") -> logging.Logger:
    logger = logging.getLogger(name)
    if not any(isinstance(h.formatter, RedactingJsonFormatter) for h in logger.handlers):
        h = logging.StreamHandler()
        h.setFormatter(RedactingJsonFormatter())
        logger.addHandler(h)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger
