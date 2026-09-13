"""Application exception hierarchy.

All domain and infrastructure errors derive from :class:`AiAgentError`. The API
layer maps ``status_code`` / ``error_code`` to the response envelope
(``api/envelope.py``) so handlers never need to know about HTTP details.
"""

from __future__ import annotations

from typing import Any


class AiAgentError(Exception):
    """Base error for the whole application."""

    status_code: int = 500
    error_code: str = "internal_error"

    def __init__(self, message: str, *, details: Any | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


class ConfigurationError(AiAgentError):
    """Invalid or unreadable configuration (YAML or environment overrides)."""

    status_code = 500
    error_code = "configuration_error"


class DatabaseError(AiAgentError):
    """Base class for database-layer failures."""

    status_code = 500
    error_code = "database_error"


class DatabaseConnectionError(DatabaseError):
    """The database is unreachable or misconfigured."""

    status_code = 503
    error_code = "database_unavailable"


class NotFoundError(AiAgentError):
    """A requested resource does not exist."""

    status_code = 404
    error_code = "not_found"


class ConflictError(AiAgentError):
    """The request conflicts with the current state of the resource."""

    status_code = 409
    error_code = "conflict"


class InvalidStateError(AiAgentError):
    """A state transition is not permitted by the entity's state machine."""

    status_code = 409
    error_code = "invalid_state"


class PolicyViolationError(AiAgentError):
    """The configuration violates a least-privilege / security policy."""

    status_code = 403
    error_code = "policy_violation"


class AgentNotExecutableError(AiAgentError):
    """The agent cannot be executed (inactive, disabled, or missing)."""

    status_code = 403
    error_code = "agent_not_executable"


class PermissionDeniedError(AiAgentError):
    """A capability, tool, or permission check failed."""

    status_code = 403
    error_code = "permission_denied"


class InvalidExecutionContextError(AiAgentError):
    """The execution context contains invalid references (project, task, etc.)."""

    status_code = 422
    error_code = "invalid_execution_context"


class PayloadTooLargeError(AiAgentError):
    """Input or output exceeds the configured size limits."""

    status_code = 413
    error_code = "payload_too_large"
