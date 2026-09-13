"""Typed domain-event contract consumed by services and (later) the event bus.

The outbox pattern in STEP 2 already persists ``Event`` documents in a
``pending`` state.  This module defines the *application-side* event shapes
that services emit; :class:`EventPublisher` maps them to the ``Event``
document when persisting.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from aiagent.core.context import get_request_context
from aiagent.db.base import utcnow
from aiagent.db.constants import EventStatus


class EventType(StrEnum):
    """Canonical event names emitted by the service layer."""

    # project lifecycle
    PROJECT_CREATED = "project.created"
    PROJECT_UPDATED = "project.updated"
    # agent registry
    AGENT_CREATED = "agent.created"
    AGENT_UPDATED = "agent.updated"
    AGENT_ENABLED = "agent.enabled"
    AGENT_DISABLED = "agent.disabled"
    AGENT_DEPRECATED = "agent.deprecated"
    AGENT_PERMISSIONS_CHANGED = "agent.permissions_changed"
    AGENT_MODEL_CHANGED = "agent.model_changed"
    AGENT_AUTONOMY_CHANGED = "agent.autonomy_changed"
    # task lifecycle
    TASK_CREATED = "task.created"
    TASK_UPDATED = "task.updated"
    # task run (per-attempt lease)
    TASK_RUN_STARTED = "task_run.started"
    TASK_RUN_COMPLETED = "task_run.completed"
    TASK_RUN_FAILED = "task_run.failed"
    # workflow definitions
    WORKFLOW_REGISTERED = "workflow.registered"
    WORKFLOW_UPDATED = "workflow.updated"
    # workflow runs
    WORKFLOW_RUN_CREATED = "workflow_run.created"


class DomainEvent(BaseModel):
    """Application-level event payload; maps directly to an ``Event`` doc."""

    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    type: EventType
    payload: dict[str, Any] = Field(default_factory=dict)
    project_id: str | None = None
    emitted_by: str | None = None
    trace_id: str | None = None
    emitted_at: datetime = Field(default_factory=utcnow)
    status: EventStatus = EventStatus.PENDING

    @classmethod
    def build(
        cls,
        event_type: EventType,
        *,
        payload: dict[str, Any] | None = None,
        project_id: str | None = None,
        emitted_by: str | None = None,
        trace_id: str | None = None,
    ) -> DomainEvent:
        """Convenience factory that pulls ``trace_id`` from request context."""
        _, current_tid = get_request_context()
        return cls(
            type=event_type,
            payload=payload or {},
            project_id=project_id,
            emitted_by=emitted_by,
            trace_id=trace_id or current_tid or None,
        )
