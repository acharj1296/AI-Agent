"""Per-request context carried through contextvars.

``trace_id`` and ``request_id`` are generated per request by the API middleware
and surface in every structured log line so a single request can be traced end
to end without threading parameters through call stacks.
"""

from __future__ import annotations

import uuid
from contextvars import ContextVar

request_id_var: ContextVar[str] = ContextVar("request_id", default="")
trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")


def new_id() -> str:
    """Return a short random hex id (32 chars)."""
    return uuid.uuid4().hex


def set_request_context(
    *, request_id: str | None = None, trace_id: str | None = None
) -> tuple[str, str]:
    """Populate the contextvars and return the effective (request_id, trace_id)."""
    rid = request_id or new_id()
    tid = trace_id or new_id()
    request_id_var.set(rid)
    trace_id_var.set(tid)
    return rid, tid


def get_request_context() -> tuple[str, str]:
    """Return the current (request_id, trace_id); empty strings if unset."""
    return request_id_var.get(), trace_id_var.get()


def clear_request_context() -> None:
    """Reset the contextvars (after request completion / in tests)."""
    request_id_var.set("")
    trace_id_var.set("")
