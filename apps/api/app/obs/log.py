"""One structured log line. Unknown fields are dropped, including secrets."""

from __future__ import annotations

import json
import logging
import sys
from typing import Any

LOG_FIELDS = (
    "requestId",
    "investigationId",
    "tenant",
    "step",
    "tool",
    "queryId",
    "durationMs",
    "resultCount",
    "status",
    "errorCategory",
)

_TEXT_FIELDS = {
    "requestId",
    "investigationId",
    "tenant",
    "step",
    "tool",
    "queryId",
    "status",
    "errorCategory",
}
_COUNT_FIELDS = {"durationMs", "resultCount"}

LOGGER_NAME = "graphops"


def configure_logging(level: str) -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)
    logger.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.setLevel(level.upper())
    logger.propagate = False
    return logger


def log_step(logger: logging.Logger, /, **fields: Any) -> str:
    """Emit one JSON line containing only the allowlisted step fields."""

    payload = {name: _coerce(name, fields.get(name)) for name in LOG_FIELDS}
    line = json.dumps(payload, separators=(",", ":"), ensure_ascii=True)
    logger.info(line)
    return line


def _coerce(name: str, value: object) -> str | int | None:
    if name in _TEXT_FIELDS:
        if isinstance(value, str):
            return value
        return None
    if name in _COUNT_FIELDS:
        if isinstance(value, bool) or not isinstance(value, int):
            return None
        return value
    return None
