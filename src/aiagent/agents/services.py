"""Agent registry service.

Manages the lifecycle of agent definitions (docs/plan/04 §1).
Register/update only — runtime execution lives in a later step.
"""

from __future__ import annotations

from typing import Any

from aiagent.core.errors import ConflictError, NotFoundError
from aiagent.db.models import Agent
from aiagent.db.repositories import Repositories
from aiagent.events.audit import AuditLogger, snapshot
from aiagent.events.publisher import EventPublisher
from aiagent.events.types import DomainEvent, EventType


class AgentService:
    def __init__(
        self,
        repos: Repositories,
        publisher: EventPublisher,
        audit: AuditLogger,
    ) -> None:
        self._repos = repos
        self._publisher = publisher
        self._audit = audit

    async def register_agent(
        self,
        *,
        agent_id: str,
        department: str | None = None,
        name: str | None = None,
        config: dict[str, Any] | None = None,
    ) -> Agent:
        existing = await self._repos.agents.find_by_agent_id(agent_id)
        if existing is not None:
            raise ConflictError(f"agent {agent_id!r} already registered")

        agent = Agent(agent_id=agent_id, department=department, name=name, config=config or {})
        await self._repos.agents.create(agent)

        await self._publisher.publish(
            DomainEvent.build(
                EventType.AGENT_CREATED,
                payload={"agent_id": agent.agent_id},
                emitted_by="service:agent",
            )
        )
        await self._audit.record(
            action="agent.create",
            resource_type="agent",
            resource_id=agent.id,
            after=snapshot(agent),
        )
        return agent

    async def update_agent(
        self,
        doc_id: str,
        *,
        department: str | None = None,
        name: str | None = None,
        config: dict[str, Any] | None = None,
    ) -> Agent:
        current = await self._repos.agents.find_by_id(doc_id)
        if current is None:
            raise NotFoundError(f"agent {doc_id} not found")

        changes: dict[str, Any] = {}
        if department is not None:
            changes["department"] = department
        if name is not None:
            changes["name"] = name
        if config is not None:
            changes["config"] = config

        updated = await self._repos.agents.update(doc_id, changes)
        if updated is None:
            raise NotFoundError(f"agent {doc_id} not found")

        await self._publisher.publish(
            DomainEvent.build(
                EventType.AGENT_UPDATED,
                payload={"agent_id": current.agent_id},
                emitted_by="service:agent",
            )
        )
        await self._audit.record(
            action="agent.update",
            resource_type="agent",
            resource_id=doc_id,
            before=snapshot(current),
            after=snapshot(updated),
        )
        return updated
