"""Structured JSON logging on top of the standard library.

Every log line is a JSON object with an ISO timestamp, level, logger name and
message, plus ``request_id`` / ``trace_id`` injected from the current context. No
third-party logging dependency is required; see docs/plan/31_TECH_STACK.md.
"""

from __future__ import annotations

import json
import logging
import sys
from typing import Any

from aiagent.core import context

_RESERVED_ATTRS = frozenset(
    {
        "asctime",
        "args",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "module",
        "msecs",
        "msg",
        "message",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "taskName",
        "thread",
        "threadName",
    }
)


class JsonFormatter(logging.Formatter):
    """Format :class:`logging.LogRecord` as a single JSON line."""

    def __init__(
        self,
        *,
        include_exc_info: bool = True,
        extra_fields: bool = True,
    ) -> None:
        super().__init__()
        self.include_exc_info = include_exc_info
        self.extra_fields = extra_fields

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
            "module": record.module,
            "line": record.lineno,
        }

        request_id, trace_id = context.get_request_context()
        if request_id:
            payload["request_id"] = request_id
        if trace_id:
            payload["trace_id"] = trace_id

        if self.extra_fields:
            for key, value in record.__dict__.items():
                if key not in _RESERVED_ATTRS:
                    payload[key] = value

        if record.exc_info and self.include_exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)

        if record.stack_info:
            payload["stack"] = self.formatStack(record.stack_info)

        return json.dumps(payload, default=_json_default)

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        return super().formatTime(record, datefmt)


class _PlainFormatter(logging.Formatter):
    """Readable single-line formatter for non-JSON (debug) output."""

    _FMT = "%(asctime)s %(levelname)-7s [%(name)s] %(message)s"

    def __init__(self, *, include_exc_info: bool = True) -> None:
        super().__init__(fmt=self._FMT, datefmt="%Y-%m-%dT%H:%M:%S%z")
        self.include_exc_info = include_exc_info


def _json_default(value: Any) -> str:
    try:
        return str(value)
    except Exception:  # pragma: no cover - defensive
        return repr(value)


def setup_logging(
    *,
    level: int | str = logging.INFO,
    json: bool = True,
    logger_name: str = "aiagent",
) -> None:
    """Configure root logging with a single console handler.

    Uvicorn loggers are reset and propagate to the root so requests, errors and
    app logs all flow through the same JSON formatter.
    """
    if isinstance(level, str):
        level = level.upper()
        resolved = getattr(logging, level, None)
        if not isinstance(resolved, int):
            raise ValueError(f"Unknown log level: {level}")
        level = resolved

    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(JsonFormatter() if json else _PlainFormatter())

    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)

    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.handlers[:] = []
        logger.propagate = True

    logging.getLogger(logger_name).setLevel(level)


def get_logger(name: str = "") -> logging.Logger:
    """Return a child logger of the ``aiagent`` namespace."""
    if name and not name.startswith("aiagent."):
        name = f"aiagent.{name}"
    return logging.getLogger(name or "aiagent")
