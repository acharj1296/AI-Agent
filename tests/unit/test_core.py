"""Unit tests for request context, logging, and errors."""

from __future__ import annotations

import json
import logging

from aiagent.core import context
from aiagent.core.errors import (
    AiAgentError,
    ConfigurationError,
    DatabaseConnectionError,
    DatabaseError,
    NotFoundError,
)
from aiagent.core.logging import JsonFormatter, get_logger, setup_logging


def test_new_id_is_32_hex_chars() -> None:
    value = context.new_id()
    assert len(value) == 32
    assert set(value) <= set("0123456789abcdef")


def test_set_get_clear_context() -> None:
    context.set_request_context(request_id="rid-1", trace_id="tid-1")
    assert context.get_request_context() == ("rid-1", "tid-1")
    context.clear_request_context()
    assert context.get_request_context() == ("", "")


def test_auto_generated_context_ids_differ() -> None:
    rid, tid = context.set_request_context()
    assert rid and tid
    assert rid != tid
    context.clear_request_context()
    rid2, _ = context.set_request_context()
    assert rid != rid2
    context.clear_request_context()


def test_error_hierarchy() -> None:
    assert issubclass(ConfigurationError, AiAgentError)
    assert issubclass(DatabaseConnectionError, DatabaseError)
    assert issubclass(NotFoundError, AiAgentError)
    err = NotFoundError("missing", details={"id": 1})
    assert err.status_code == 404
    assert err.error_code == "not_found"
    assert err.details == {"id": 1}


def test_json_formatter_includes_context_ids() -> None:
    context.set_request_context(request_id="R-1", trace_id="T-1")
    try:
        record = logging.LogRecord(
            "aiagent.test", logging.INFO, "m.py", 1, "hello %s", ("world",), None
        )
        line = JsonFormatter().format(record)
        payload = json.loads(line)
        assert payload["event"] == "hello world"
        assert payload["level"] == "INFO"
        assert payload["logger"] == "aiagent.test"
        assert payload["request_id"] == "R-1"
        assert payload["trace_id"] == "T-1"
    finally:
        context.clear_request_context()


def test_json_formatter_includes_extra_fields() -> None:
    record = logging.LogRecord("aiagent.test", logging.INFO, "m.py", 1, "msg", (), None)
    record.foo = "bar"
    payload = json.loads(JsonFormatter().format(record))
    assert payload["foo"] == "bar"


def test_setup_logging_installs_single_json_handler() -> None:
    setup_logging(level=logging.INFO, json=True)
    root = logging.getLogger()
    assert len(root.handlers) == 1
    assert isinstance(root.handlers[0].formatter, JsonFormatter)


def test_setup_logging_rejects_bad_level() -> None:
    try:
        setup_logging(level="NOT_A_LEVEL")
    except ValueError:
        return
    raise AssertionError("expected ValueError for invalid level")


def test_get_logger_namespace() -> None:
    assert get_logger("db").name == "aiagent.db"
    assert get_logger("aiagent.direct").name == "aiagent.direct"
