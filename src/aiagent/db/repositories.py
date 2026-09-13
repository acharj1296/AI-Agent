"""Repository / data-access layer (Application -> Repository -> MongoDB).

Repositories are deliberately thin: they own collection access and simple
CRUD/lookups only.  Business logic must live in the service layer that will
sit on top of these repositories in later steps.

Every write re-validates the document through its pydantic model, so invalid
or out-of-enum data is rejected before it reaches MongoDB.  MongoDB native
errors are translated into safe application-level errors
(:mod:`aiagent.core.errors`) - raw driver errors never leak to callers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from motor.motor_asyncio import AsyncIOMotorCollection, AsyncIOMotorDatabase
from pymongo import ReturnDocument
from pymongo.errors import (
    AutoReconnect,
    ConnectionFailure,
    DuplicateKeyError,
    NetworkTimeout,
    OperationFailure,
    PyMongoError,
    ServerSelectionTimeoutError,
)

from aiagent.core.errors import (
    AiAgentError,
    ConflictError,
    DatabaseConnectionError,
    DatabaseError,
)
from aiagent.db.base import BaseDocument, utcnow
from aiagent.db.models import (
    Agent,
    AgentRun,
    Approval,
    Artifact,
    AuditLog,
    Event,
    Memory,
    Message,
    Model,
    Organization,
    Project,
    Review,
    Task,
    TaskRun,
    ToolCall,
    User,
    Workflow,
    WorkflowRun,
)

_COLLECTION_LABEL = {
    "organizations": "organization",
    "users": "user",
    "projects": "project",
    "agents": "agent",
    "agent_runs": "agent run",
    "tasks": "task",
    "task_runs": "task run",
    "workflow_runs": "workflow run",
    "workflows": "workflow",
    "artifacts": "artifact",
    "messages": "message",
    "memories": "memory",
    "approvals": "approval",
    "reviews": "review",
    "tool_calls": "tool call",
    "models": "model",
    "events": "event",
    "audit_logs": "audit log",
}


def _translate(collection: str, exc: PyMongoError) -> AiAgentError:
    label = _COLLECTION_LABEL.get(collection, "document")
    if isinstance(exc, DuplicateKeyError):
        field = _duplicate_field(exc)
        details: dict[str, Any] = {"collection": collection}
        if field:
            details["field"] = field
        return ConflictError(
            f"{label} with the same {field or 'value'} already exists", details=details
        )
    if isinstance(
        exc, (ServerSelectionTimeoutError, NetworkTimeout, AutoReconnect, ConnectionFailure)
    ):
        return DatabaseConnectionError(f"database unavailable ({label})")
    if isinstance(exc, OperationFailure):
        return DatabaseError(f"database operation failed on {label}")
    return DatabaseError(f"database operation failed on {label}")


def _duplicate_field(exc: DuplicateKeyError) -> str | None:
    details = getattr(exc, "details", None) or {}
    key_pattern = details.get("keyPattern")
    if isinstance(key_pattern, dict) and key_pattern:
        return next(iter(key_pattern))
    return None


@dataclass(frozen=True)
class Page[T]:
    """A single page of results from :meth:`Repository.paginate`."""

    items: list[T]
    total: int
    page: int
    page_size: int

    @property
    def has_next(self) -> bool:
        return self.page * self.page_size < self.total


class Repository[T: BaseDocument]:
    """Generic CRUD over a single collection, typed to a document model."""

    def __init__(self, db: AsyncIOMotorDatabase, model: type[T]) -> None:
        self._db = db
        self._model = model

    @property
    def collection(self) -> AsyncIOMotorCollection:
        return self._db[self._model.collection]

    async def create(self, document: T) -> T:
        """Insert a validated document; raises :class:`ConflictError` on duplicates."""
        try:
            await self.collection.insert_one(document.to_doc())
        except PyMongoError as exc:
            raise _translate(self._model.collection, exc) from exc
        return document

    async def find_by_id(self, doc_id: str) -> T | None:
        doc = await self.collection.find_one({"_id": doc_id})
        return self._model.from_doc(doc) if doc else None

    async def find_one(self, query: dict[str, Any]) -> T | None:
        doc = await self.collection.find_one(query)
        return self._model.from_doc(doc) if doc else None

    async def find_many(
        self,
        query: dict[str, Any] | None = None,
        *,
        sort: list[tuple[str, int]] | None = None,
        limit: int = 0,
        skip: int = 0,
    ) -> list[T]:
        cursor = self.collection.find(query or {})
        if sort:
            cursor = cursor.sort(sort)
        if skip:
            cursor = cursor.skip(skip)
        if limit:
            cursor = cursor.limit(limit)
        docs = [doc async for doc in cursor]
        return [self._model.from_doc(doc) for doc in docs]

    async def update(self, doc_id: str, changes: dict[str, Any]) -> T | None:
        """Apply ``$set`` updates, re-validating the merged document.

        Returns the updated document (or ``None`` when the id does not exist).
        Only fields present in ``changes`` are persisted (plus ``updated_at``).
        """
        current = await self.collection.find_one({"_id": doc_id})
        if current is None:
            return None
        merged = {**current, **changes}
        if "_id" in merged:
            merged["id"] = str(merged.pop("_id"))
        self._model.model_validate(merged)  # reject invalid data
        patch: dict[str, Any] = {"updated_at": utcnow(), **changes}
        try:
            result = await self.collection.find_one_and_update(
                {"_id": doc_id}, {"$set": patch}, return_document=ReturnDocument.AFTER
            )
        except PyMongoError as exc:
            raise _translate(self._model.collection, exc) from exc
        return self._model.from_doc(result) if result else None

    async def delete(self, doc_id: str) -> bool:
        result = await self.collection.delete_one({"_id": doc_id})
        return result.deleted_count == 1

    async def exists(self, query: dict[str, Any]) -> bool:
        return await self.collection.find_one(query, projection={"_id": 1}) is not None

    async def count(self, query: dict[str, Any] | None = None) -> int:
        return await self.collection.count_documents(query or {})

    async def paginate(
        self,
        query: dict[str, Any] | None = None,
        *,
        sort: list[tuple[str, int]] | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Page[T]:
        """Return one page of results plus the total match count.

        Pages are 1-based; ``page_size`` is clamped to a sane upper bound.
        ``has_next`` is derived from ``page * page_size < total`` so callers
        never need an extra query to detect the last page.
        """
        page = max(1, page)
        page_size = min(max(1, page_size), 200)
        total = await self.count(query)
        items = await self.find_many(
            query,
            sort=sort,
            limit=page_size,
            skip=(page - 1) * page_size,
        )
        return Page(items=items, total=total, page=page, page_size=page_size)


class OrganizationRepository(Repository[Organization]):
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        super().__init__(db, Organization)


class UserRepository(Repository[User]):
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        super().__init__(db, User)

    async def find_by_email(self, email: str) -> User | None:
        return await self.find_one({"email": email.lower()})

    async def find_by_org(self, org_id: str) -> list[User]:
        return await self.find_many({"org_id": org_id}, sort=[("created_at", 1)])


class ProjectRepository(Repository[Project]):
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        super().__init__(db, Project)

    async def find_by_org(self, org_id: str, *, status: str | None = None) -> list[Project]:
        query: dict[str, Any] = {"org_id": org_id}
        if status:
            query["status"] = status
        return await self.find_many(query, sort=[("created_at", -1)])


class AgentRepository(Repository[Agent]):
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        super().__init__(db, Agent)

    async def find_by_agent_id(self, agent_id: str) -> Agent | None:
        return await self.find_one({"agent_id": agent_id})

    async def find_by_slug(self, slug: str) -> Agent | None:
        return await self.find_one({"slug": slug})

    async def find_by_department(
        self, department: str, *, status: str | None = None
    ) -> list[Agent]:
        query: dict[str, Any] = {"department": department}
        if status:
            query["status"] = status
        return await self.find_many(query, sort=[("created_at", 1)])

    async def find_by_role(self, role: str, *, status: str | None = None) -> list[Agent]:
        query: dict[str, Any] = {"role": role}
        if status:
            query["status"] = status
        return await self.find_many(query, sort=[("created_at", 1)])

    async def find_by_capability(
        self, capability: str, *, status: str | None = None
    ) -> list[Agent]:
        query: dict[str, Any] = {"capabilities": capability}
        if status:
            query["status"] = status
        return await self.find_many(query, sort=[("created_at", 1)])

    async def count_by_status(self, status: str) -> int:
        return await self.count({"status": status})


class AgentRunRepository(Repository[AgentRun]):
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        super().__init__(db, AgentRun)

    async def find_by_task(self, task_id: str) -> list[AgentRun]:
        return await self.find_many({"task_id": task_id}, sort=[("created_at", -1)])


class TaskRepository(Repository[Task]):
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        super().__init__(db, Task)

    async def find_by_project(self, project_id: str, *, status: str | None = None) -> list[Task]:
        query: dict[str, Any] = {"project_id": project_id}
        if status:
            query["status"] = status
        return await self.find_many(query, sort=[("created_at", 1)])


class WorkflowRunRepository(Repository[WorkflowRun]):
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        super().__init__(db, WorkflowRun)

    async def find_by_project(
        self, project_id: str, *, status: str | None = None
    ) -> list[WorkflowRun]:
        query: dict[str, Any] = {"project_id": project_id}
        if status:
            query["status"] = status
        return await self.find_many(query, sort=[("created_at", -1)])


class WorkflowRepository(Repository[Workflow]):
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        super().__init__(db, Workflow)

    async def find_by_id_version(
        self, workflow_id: str, version: int | None = None
    ) -> Workflow | None:
        query: dict[str, Any] = {"workflow_id": workflow_id}
        if version is not None:
            query["version"] = version
            return await self.find_one(query)
        docs = await self.find_many(query, sort=[("version", -1)], limit=1)
        return docs[0] if docs else None

    async def find_active(self) -> list[Workflow]:
        return await self.find_many({"status": "active"}, sort=[("created_at", -1)])


class TaskRunRepository(Repository[TaskRun]):
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        super().__init__(db, TaskRun)

    async def find_by_task(self, task_id: str) -> list[TaskRun]:
        return await self.find_many({"task_id": task_id}, sort=[("attempt", -1)])

    async def next_attempt(self, task_id: str) -> int:
        latest = await self.find_many({"task_id": task_id}, sort=[("attempt", -1)], limit=1)
        return (latest[0].attempt + 1) if latest else 1


class ArtifactRepository(Repository[Artifact]):
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        super().__init__(db, Artifact)

    async def find_by_project(self, project_id: str, *, kind: str | None = None) -> list[Artifact]:
        query: dict[str, Any] = {"project_id": project_id}
        if kind:
            query["kind"] = kind
        return await self.find_many(query, sort=[("created_at", -1)])


class MessageRepository(Repository[Message]):
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        super().__init__(db, Message)

    async def find_undelivered(self, recipient: str) -> list[Message]:
        return await self.find_many({"recipient": recipient, "status": "pending"})


class MemoryRepository(Repository[Memory]):
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        super().__init__(db, Memory)

    async def find_by_project(self, project_id: str, kind: str | None = None) -> list[Memory]:
        query: dict[str, Any] = {"project_id": project_id}
        if kind:
            query["kind"] = kind
        return await self.find_many(query, sort=[("created_at", -1)])


class ApprovalRepository(Repository[Approval]):
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        super().__init__(db, Approval)

    async def find_pending_by_project(self, project_id: str) -> list[Approval]:
        return await self.find_many({"project_id": project_id, "status": "pending"})


class ReviewRepository(Repository[Review]):
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        super().__init__(db, Review)


class ToolCallRepository(Repository[ToolCall]):
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        super().__init__(db, ToolCall)


class ModelRepository(Repository[Model]):
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        super().__init__(db, Model)


class EventRepository(Repository[Event]):
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        super().__init__(db, Event)


class AuditLogRepository(Repository[AuditLog]):
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        super().__init__(db, AuditLog)


class Repositories:
    """Data-access facade exposing every MongoDB repository.

    Services (added in later steps) depend on this object instead of touching
    collections directly, keeping the layering clean.
    """

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self.organizations = OrganizationRepository(db)
        self.users = UserRepository(db)
        self.projects = ProjectRepository(db)
        self.agents = AgentRepository(db)
        self.agent_runs = AgentRunRepository(db)
        self.tasks = TaskRepository(db)
        self.task_runs = TaskRunRepository(db)
        self.workflow_runs = WorkflowRunRepository(db)
        self.workflows = WorkflowRepository(db)
        self.artifacts = ArtifactRepository(db)
        self.messages = MessageRepository(db)
        self.memories = MemoryRepository(db)
        self.approvals = ApprovalRepository(db)
        self.reviews = ReviewRepository(db)
        self.tool_calls = ToolCallRepository(db)
        self.models = ModelRepository(db)
        self.events = EventRepository(db)
        self.audit_logs = AuditLogRepository(db)
