"""Response envelope builders (docs/plan/29 section 4).

Success:  ``{"ok": true, "data": ..., "meta": {...}, "trace_id": "..."}``
Error:    ``{"ok": false, "error": {"code": "...", "message": "...",
           "details": {...}}, "trace_id": "..."}``
"""

from __future__ import annotations

from typing import Any

from aiagent.core import context


def ok(data: Any = None, *, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build a success envelope carrying the current trace id."""
    return {
        "ok": True,
        "data": data,
        "meta": meta or {},
        "trace_id": context.get_request_context()[1],
    }


def error(*, code: str, message: str, details: Any = None) -> dict[str, Any]:
    """Build an error envelope carrying the current trace id."""
    payload: dict[str, Any] = {
        "code": code,
        "message": message,
    }
    if details is not None:
        payload["details"] = details
    return {
        "ok": False,
        "error": payload,
        "trace_id": context.get_request_context()[1],
    }
