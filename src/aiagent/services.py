"""Composition root for the service layer.

``build_service_layer(db)`` assembles every repository-backed service plus the
event publisher and audit logger they share.  FastAPI routers consume this
through ``aiagent.api.deps.ServicesDep``; module boundaries stay intact because
each service only talks to repositories, events and audit.
"""

from __future__ import annotations

from dataclasses import dataclass

from motor.motor_asyncio import AsyncIOMotorDatabase

from aiagent.agents.services import AgentService
from aiagent.db.repositories import Repositories
from aiagent.events.audit import AuditLogger
from aiagent.events.publisher import EventPublisher
from aiagent.projects.services import ProjectService
from aiagent.tasks.services import TaskService
from aiagent.workflow.services import WorkflowService


@dataclass(frozen=True)
class ServiceLayer:
    """Handles to every service, ready for injection into API routers."""

    projects: ProjectService
    agents: AgentService
    tasks: TaskService
    workflows: WorkflowService


def build_service_layer(database: AsyncIOMotorDatabase) -> ServiceLayer:
    repos = Repositories(database)
    publisher = EventPublisher(repos.events)
    audit = AuditLogger(repos.audit_logs)
    return ServiceLayer(
        projects=ProjectService(repos, publisher, audit),
        agents=AgentService(repos, publisher, audit),
        tasks=TaskService(repos, publisher, audit),
        workflows=WorkflowService(repos, publisher, audit),
    )
