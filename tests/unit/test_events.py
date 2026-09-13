"""Unit tests for the STEP 3 event contract and pagination metadata."""

from __future__ import annotations

from aiagent.core.context import clear_request_context, set_request_context
from aiagent.db.constants import EventStatus
from aiagent.db.repositories import Page
from aiagent.events.types import DomainEvent, EventType


def test_event_type_values() -> None:
    assert EventType.PROJECT_CREATED == "project.created"
    assert EventType.TASK_RUN_STARTED == "task_run.started"
    assert EventType.WORKFLOW_REGISTERED == "workflow.registered"


def test_domain_event_defaults() -> None:
    clear_request_context()
    event = DomainEvent.build(EventType.TASK_CREATED, payload={"task_id": "abc"})
    assert len(event.event_id) == 32
    assert event.payload == {"task_id": "abc"}
    assert event.status == EventStatus.PENDING
    assert event.trace_id is None
    assert event.project_id is None


def test_domain_event_build_pulls_trace_from_context() -> None:
    set_request_context(request_id="rid1", trace_id="tid1")
    event = DomainEvent.build(
        EventType.PROJECT_CREATED,
        payload={"project_id": "p1"},
        project_id="p1",
        emitted_by="service:project",
    )
    assert event.trace_id == "tid1"
    assert event.emitted_by == "service:project"
    assert event.type is EventType.PROJECT_CREATED
    clear_request_context()


def test_domain_event_rejects_unknown_fields() -> None:
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        DomainEvent(type=EventType.PROJECT_CREATED, surprise=1)


def test_page_has_next_math() -> None:
    assert Page(items=[], total=0, page=1, page_size=20).has_next is False
    assert Page(items=[], total=20, page=1, page_size=20).has_next is False
    assert Page(items=[], total=21, page=1, page_size=20).has_next is True
    assert Page(items=[], total=21, page=2, page_size=20).has_next is False
