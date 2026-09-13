"""Task service: task lifecycle + per-attempt (TaskRun) lease records.

Implements the first rungs of the task state machine (docs/plan/08 §3-4):
- create a task with reference-integrity check against the owning project,
- start an attempt (TaskRun) with idempotent attempt-number detection,
- finish an attempt with status-specific event emission.

No queue, no worker pool, no dependency DAG — those are later steps.
"""

from __future__ import annotations

from typing import Any

from aiagent.core.errors import ConflictError, NotFoundError
from aiagent.db.base import utcnow
from aiagent.db.constants import TaskPriority, TaskRunStatus
from aiagent.db.models import Task, TaskRun
from aiagent.db.repositories import Repositories
from aiagent.events.audit import AuditLogger, snapshot
from aiagent.events.publisher import EventPublisher
from aiagent.events.types import DomainEvent, EventType


class TaskService:
    def __init__(
        self,
        repos: Repositories,
        publisher: EventPublisher,
        audit: AuditLogger,
    ) -> None:
        self._repos = repos
        self._publisher = publisher
        self._audit = audit

    async def create_task(
        self,
        *,
        project_id: str,
        task_type: str,
        title: str,
        description: str | None = None,
        priority: TaskPriority = TaskPriority.MEDIUM,
        parent_task_id: str | None = None,
        assigned_agent_id: str | None = None,
        reviewer_agent_id: str | None = None,
        dependencies: list[str] | None = None,
        expected_outputs: list[str] | None = None,
    ) -> Task:
        if await self._repos.projects.find_by_id(project_id) is None:
            raise NotFoundError(f"project {project_id} not found")

        task = Task(
            project_id=project_id,
            type=task_type,
            title=title,
            description=description,
            priority=priority,
            parent_task_id=parent_task_id,
            assigned_agent_id=assigned_agent_id,
            reviewer_agent_id=reviewer_agent_id,
            dependencies=dependencies or [],
            expected_outputs=expected_outputs or [],
        )
        await self._repos.tasks.create(task)

        await self._publisher.publish(
            DomainEvent.build(
                EventType.TASK_CREATED,
                payload={"task_id": task.id, "project_id": project_id, "type": task.type},
                project_id=project_id,
                emitted_by="service:task",
            )
        )
        await self._audit.record(
            action="task.create",
            project_id=project_id,
            resource_type="task",
            resource_id=task.id,
            after=snapshot(task),
        )
        return task

    async def start_task_run(
        self,
        *,
        task_id: str,
        attempt: int | None = None,
        worker_id: str | None = None,
        agent_run_id: str | None = None,
    ) -> TaskRun:
        task = await self._repos.tasks.find_by_id(task_id)
        if task is None:
            raise NotFoundError(f"task {task_id} not found")

        attempt = attempt or await self._repos.task_runs.next_attempt(task_id)
        run = TaskRun(
            task_id=task_id,
            project_id=task.project_id,
            attempt=attempt,
            status=TaskRunStatus.RUNNING,
            worker_id=worker_id,
            agent_run_id=agent_run_id,
            started_at=utcnow(),
        )
        try:
            await self._repos.task_runs.create(run)
        except ConflictError as exc:
            raise ConflictError(
                f"task run for task {task_id} attempt {attempt} already exists"
            ) from exc

        await self._publisher.publish(
            DomainEvent.build(
                EventType.TASK_RUN_STARTED,
                payload={"task_run_id": run.id, "task_id": task_id, "attempt": attempt},
                project_id=task.project_id,
                emitted_by="service:task",
            )
        )
        await self._audit.record(
            action="task_run.start",
            project_id=task.project_id,
            resource_type="task_run",
            resource_id=run.id,
            after=snapshot(run),
        )
        return run

    async def finish_task_run(
        self,
        run_id: str,
        *,
        status: TaskRunStatus,
        error_detail: dict[str, Any] | None = None,
    ) -> TaskRun:
        current = await self._repos.task_runs.find_by_id(run_id)
        if current is None:
            raise NotFoundError(f"task run {run_id} not found")

        terminal = status in {
            TaskRunStatus.SUCCEEDED,
            TaskRunStatus.FAILED,
            TaskRunStatus.TIMEOUT,
            TaskRunStatus.CANCELLED,
        }
        changes: dict[str, Any] = {"status": status}
        if terminal:
            changes["completed_at"] = utcnow()
        if error_detail is not None:
            changes["error_detail"] = error_detail

        updated = await self._repos.task_runs.update(run_id, changes)
        if updated is None:
            raise NotFoundError(f"task run {run_id} not found")

        event_type = (
            EventType.TASK_RUN_COMPLETED
            if status == TaskRunStatus.SUCCEEDED
            else EventType.TASK_RUN_FAILED
        )
        await self._publisher.publish(
            DomainEvent.build(
                event_type,
                payload={
                    "task_run_id": run_id,
                    "task_id": current.task_id,
                    "attempt": current.attempt,
                },
                project_id=current.project_id,
                emitted_by="service:task",
            )
        )
        await self._audit.record(
            action="task_run.finish",
            project_id=current.project_id,
            resource_type="task_run",
            resource_id=run_id,
            before=snapshot(current),
            after=snapshot(updated),
        )
        return updated
