"""Project service: onboarding + project-state operations on top of repositories.

Owning module for ``projects`` state (docs/plan/13).  Business rules enforced
here (reference integrity, event emission, audit) keep the repository layer
thin.  The orchestrator stage machine lands in this module's later steps.
"""

from __future__ import annotations

from typing import Any

from aiagent.core.errors import NotFoundError
from aiagent.db.models import Organization, Project
from aiagent.db.repositories import Page, Repositories
from aiagent.events.audit import AuditLogger, snapshot
from aiagent.events.publisher import EventPublisher
from aiagent.events.types import DomainEvent, EventType


class ProjectService:
    def __init__(
        self,
        repos: Repositories,
        publisher: EventPublisher,
        audit: AuditLogger,
    ) -> None:
        self._repos = repos
        self._publisher = publisher
        self._audit = audit

    async def create_project(
        self,
        *,
        org_id: str,
        name: str,
        description: str | None = None,
        autonomy_level: int = 0,
        config: dict[str, Any] | None = None,
        owners: list[str] | None = None,
        decisions: list[dict[str, Any]] | None = None,
        facts: list[dict[str, Any]] | None = None,
    ) -> Project:
        """Create a new project under an existing organization ("onboarding").

        Emits ``project.created`` and audits the mutation; reference integrity
        is enforced up-front by checking the owning organization exists.
        """
        org: Organization | None = await self._repos.organizations.find_by_id(org_id)
        if org is None:
            raise NotFoundError(f"organization {org_id} not found")

        project = Project(
            org_id=org_id,
            name=name,
            description=description,
            autonomy_level=autonomy_level,
            config=config,
            owners=owners or [],
            decisions=decisions or [],
            facts=facts or [],
        )
        await self._repos.projects.create(project)

        await self._publisher.publish(
            DomainEvent.build(
                EventType.PROJECT_CREATED,
                payload={"project_id": project.id, "name": project.name, "org_id": org_id},
                project_id=project.id,
                emitted_by="service:project",
            )
        )
        await self._audit.record(
            action="project.create",
            project_id=project.id,
            resource_type="project",
            resource_id=project.id,
            after=snapshot(project),
        )
        return project

    async def change_status(self, project_id: str, status: str) -> Project:
        """Advance ``project.status``; emits ``project.updated`` + audit diff."""
        current = await self._repos.projects.find_by_id(project_id)
        if current is None:
            raise NotFoundError(f"project {project_id} not found")

        updated = await self._repos.projects.update(project_id, {"status": status})
        if updated is None:
            raise NotFoundError(f"project {project_id} not found")

        await self._publisher.publish(
            DomainEvent.build(
                EventType.PROJECT_UPDATED,
                payload={
                    "project_id": project_id,
                    "before": str(current.status),
                    "after": str(updated.status),
                },
                project_id=project_id,
                emitted_by="service:project",
            )
        )
        await self._audit.record(
            action="project.status_change",
            project_id=project_id,
            resource_type="project",
            resource_id=project_id,
            before=snapshot(current),
            after=snapshot(updated),
        )
        return updated

    async def list_projects(
        self,
        org_id: str,
        *,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Page[Project]:
        query: dict[str, Any] = {"org_id": org_id}
        if status:
            query["status"] = status
        return await self._repos.projects.paginate(
            query, sort=[("created_at", -1)], page=page, page_size=page_size
        )
