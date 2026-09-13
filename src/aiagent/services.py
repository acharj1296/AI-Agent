"""Composition root for the service layer.

``build_service_layer(db)`` assembles every repository-backed service plus the
event publisher and audit logger they share.  FastAPI routers consume this
through ``aiagent.api.deps.ServicesDep``; module boundaries stay intact because
each service only talks to repositories, events and audit.

The Agent Runtime (:class:`aiagent.runtime.AgentRuntimeService`) is provider-
independent: the STEP 5 distribution registers the deterministic mock provider
and a file-based instruction source; real providers are added in a later phase
without changing this wiring's shape.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from motor.motor_asyncio import AsyncIOMotorDatabase

from aiagent.agents.services import AgentRegistryService
from aiagent.core.config import get_settings
from aiagent.db.repositories import Repositories
from aiagent.events.audit import AuditLogger
from aiagent.events.publisher import EventPublisher
from aiagent.projects.services import ProjectService
from aiagent.runtime import AgentRuntimeService, ModelGateway, ModelProviderRegistry
from aiagent.runtime.content import FileContentStore
from aiagent.runtime.prompts import FileInstructionSource
from aiagent.runtime.providers.mock import DeterministicMockModelProvider
from aiagent.tasks.services import TaskService
from aiagent.workflow.services import WorkflowService


@dataclass(frozen=True)
class ServiceLayer:
    """Handles to every service, ready for injection into API routers."""

    projects: ProjectService
    agents: AgentRegistryService
    tasks: TaskService
    workflows: WorkflowService
    runtime: AgentRuntimeService


def build_service_layer(database: AsyncIOMotorDatabase) -> ServiceLayer:
    repos = Repositories(database)
    publisher = EventPublisher(repos.events)
    audit = AuditLogger(repos.audit_logs)
    settings = get_settings()

    registry = ModelProviderRegistry()
    registry.register(DeterministicMockModelProvider())
    gateway = ModelGateway(registry, settings=settings.runtime)
    instructions = FileInstructionSource(Path(settings.storage.prompts_dir).resolve())
    content = FileContentStore(Path(settings.storage.artifacts_dir).resolve())
    runtime = AgentRuntimeService(
        repos=repos,
        publisher=publisher,
        audit=audit,
        gateway=gateway,
        instructions=instructions,
        content_store=content,
        settings=settings.runtime,
    )
    return ServiceLayer(
        projects=ProjectService(repos, publisher, audit),
        agents=AgentRegistryService(repos, publisher, audit),
        tasks=TaskService(repos, publisher, audit),
        workflows=WorkflowService(repos, publisher, audit),
        runtime=runtime,
    )
