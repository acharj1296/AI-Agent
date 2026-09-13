"""Outbox-pattern event publisher.

Services call :meth:`EventPublisher.publish` with a typed :class:`DomainEvent`.
The publisher maps it to an :class:`Event` document and persists it via the
``EventRepository``.  A future dispatcher will poll pending events and deliver
them to subscribers; the application code only publishes and forgets.
"""

from __future__ import annotations

from aiagent.db.models import Event
from aiagent.db.repositories import EventRepository

from .types import DomainEvent


class EventPublisher:
    """Thin adapter that maps a typed event to the persisted ``Event`` doc."""

    def __init__(self, repository: EventRepository) -> None:
        self._repo = repository

    async def publish(self, event: DomainEvent) -> None:
        """Persist the event as a ``pending`` outbox entry."""
        doc = Event(
            type=str(event.type),
            payload=event.payload,
            project_id=event.project_id,
            emitted_by=(
                {"service": event.emitted_by, "trace_id": event.trace_id}
                if event.emitted_by or event.trace_id
                else None
            ),
            trace_id=event.trace_id,
            status=event.status,
        )
        await self._repo.create(doc)
