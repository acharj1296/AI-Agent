"""Workflow definition + run service.

Registers workflow definitions (docs/plan/07) and creates run records.
No execution engine — only the domain model operations, with events
and audit emitted for every mutation.
"""

from __future__ import annotations

from typing import Any

from aiagent.core.errors import ConflictError, NotFoundError
from aiagent.db.constants import WorkflowRunStatus
from aiagent.db.models import Workflow, WorkflowRun
from aiagent.db.repositories import Page, Repositories
from aiagent.events.audit import AuditLogger, snapshot
from aiagent.events.publisher import EventPublisher
from aiagent.events.types import DomainEvent, EventType


class WorkflowService:
    def __init__(
        self,
        repos: Repositories,
        publisher: EventPublisher,
        audit: AuditLogger,
    ) -> None:
        self._repos = repos
        self._publisher = publisher
        self._audit = audit

    async def register_workflow(
        self,
        *,
        workflow_id: str,
        name: str,
        version: int = 1,
        description: str | None = None,
        entry: str | None = None,
        steps: list[dict[str, Any]] | None = None,
    ) -> Workflow:
        existing = await self._repos.workflows.find_by_id_version(workflow_id, version)
        if existing is not None:
            raise ConflictError(f"workflow {workflow_id!r} version {version} already registered")

        wf = Workflow(
            workflow_id=workflow_id,
            name=name,
            version=version,
            description=description,
            entry=entry,
            steps=steps or [],
        )
        await self._repos.workflows.create(wf)

        await self._publisher.publish(
            DomainEvent.build(
                EventType.WORKFLOW_REGISTERED,
                payload={"workflow_id": workflow_id, "version": version},
                emitted_by="service:workflow",
            )
        )
        await self._audit.record(
            action="workflow.register",
            resource_type="workflow",
            resource_id=wf.id,
            after=snapshot(wf),
        )
        return wf

    async def list_workflows(
        self,
        *,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Page[Workflow]:
        query: dict[str, Any] = {}
        if status:
            query["status"] = status
        return await self._repos.workflows.paginate(
            query, sort=[("created_at", -1)], page=page, page_size=page_size
        )

    async def create_workflow_run(
        self,
        *,
        project_id: str,
        workflow_id: str,
        version: int | None = None,
    ) -> WorkflowRun:
        if await self._repos.projects.find_by_id(project_id) is None:
            raise NotFoundError(f"project {project_id} not found")

        definition = await self._repos.workflows.find_by_id_version(workflow_id, version)
        if definition is None:
            raise NotFoundError(f"workflow {workflow_id!r} not registered")

        run = WorkflowRun(
            project_id=project_id,
            workflow_id=workflow_id,
            status=WorkflowRunStatus.CREATED,
        )
        await self._repos.workflow_runs.create(run)

        await self._publisher.publish(
            DomainEvent.build(
                EventType.WORKFLOW_RUN_CREATED,
                payload={
                    "workflow_run_id": run.id,
                    "workflow_id": workflow_id,
                    "project_id": project_id,
                },
                project_id=project_id,
                emitted_by="service:workflow",
            )
        )
        await self._audit.record(
            action="workflow_run.create",
            project_id=project_id,
            resource_type="workflow_run",
            resource_id=run.id,
            after=snapshot(run),
        )
        return run
