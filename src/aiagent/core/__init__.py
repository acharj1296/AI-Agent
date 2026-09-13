"""core: foundational services shared by every module.

Configuration loading, structured logging with trace-id propagation,
request context via contextvars, and the application exception hierarchy.
"""

from aiagent.core.config import (
    SETTINGS_CACHE_CLEAR,
    APISettings,
    AppSettings,
    HealthSettings,
    Settings,
    get_settings,
    load_settings,
)
from aiagent.core.context import (
    clear_request_context,
    get_request_context,
    new_id,
    set_request_context,
)
from aiagent.core.errors import (
    AiAgentError,
    ConfigurationError,
    ConflictError,
    DatabaseConnectionError,
    DatabaseError,
    NotFoundError,
)
from aiagent.core.logging import JsonFormatter, get_logger, setup_logging

__all__ = [
    "SETTINGS_CACHE_CLEAR",
    "AppSettings",
    "APISettings",
    "HealthSettings",
    "Settings",
    "get_settings",
    "load_settings",
    "clear_request_context",
    "get_request_context",
    "new_id",
    "set_request_context",
    "AiAgentError",
    "ConfigurationError",
    "ConflictError",
    "DatabaseConnectionError",
    "DatabaseError",
    "NotFoundError",
    "JsonFormatter",
    "get_logger",
    "setup_logging",
]
