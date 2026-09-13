"""MongoDB document models for the MVP entity set.

Adapted from `docs/plan/28_DATABASE_DESIGN.md` and `docs/plan/13_PROJECT_STATE.md`
to MongoDB-native document design.  References between documents are by UUID
string, matching the project-wide id convention; see
`docs/plan/MONGODB_DESIGN.md` for the collection design rationale.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field, ValidationInfo, field_validator

from aiagent.db.base import BaseDocument, utcnow, validate_doc_id
from aiagent.db.constants import (
    AgentRunStatus,
    ApprovalStatus,
    ApprovalTier,
    ArtifactStatus,
    EventStatus,
    MemoryKind,
    MessageStatus,
    MessageType,
    ModelProvider,
    ProjectStage,
    ProjectStatus,
    ReviewVerdict,
    TaskPriority,
    TaskRunStatus,
    TaskStatus,
    ToolCallStatus,
    UserRole,
    WorkflowRunStatus,
    WorkflowStatus,
)

_SIMPLE_EMAIL_MARKERS = ("@", ".")


class Organization(BaseDocument):
    """Organization owning users and projects; org-wide default autonomy level."""

    collection = "organizations"

    name: str = Field(min_length=1, max_length=512)
    autonomy_default: int = Field(default=0, ge=0, le=5)
    budgets: dict[str, Any] | None = None
    settings: dict[str, Any] | None = None


class User(BaseDocument):
    """Human user bound to an organization (scoped API key hash, never raw keys)."""

    collection = "users"

    org_id: str = Field(min_length=1)
    name: str = Field(min_length=1, max_length=256)
    email: str = Field(min_length=3, max_length=512)
    role: UserRole = UserRole.ADMIN
    api_key_hash: str | None = None
    last_seen_at: datetime | None = None

    @field_validator("email")
    @classmethod
    def _email_shape(cls, value: str) -> str:
        if not all(marker in value for marker in _SIMPLE_EMAIL_MARKERS) or value.startswith("@"):
            raise ValueError(f"email does not look like an address: {value!r}")
        return value.lower()


class Project(BaseDocument):
    """Single project state store (docs/plan/13): stage, status, decisions, facts."""

    collection = "projects"

    org_id: str = Field(min_length=1)
    name: str = Field(min_length=1, max_length=512)
    description: str | None = None
    stage: ProjectStage = ProjectStage.IDEA
    status: ProjectStatus = ProjectStatus.ACTIVE
    autonomy_level: int = Field(default=0, ge=0, le=5)
    config: dict[str, Any] | None = None
    decisions: list[dict[str, Any]] = Field(default_factory=list)
    facts: list[dict[str, Any]] = Field(default_factory=list)
    owners: list[str] = Field(default_factory=list)
    current_workflow_id: str | None = None


class Agent(BaseDocument):
    """Agent definition registry (docs/plan/28 section 2.2)."""

    collection = "agents"

    agent_id: str = Field(min_length=1, max_length=256)
    department: str | None = None
    name: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)


class AgentRun(BaseDocument):
    """One agent execution attempt (docs/plan/28 section 2.3)."""

    collection = "agent_runs"

    agent_id: str = Field(min_length=1)
    task_id: str | None = None
    project_id: str | None = None
    attempt: int = Field(default=1, ge=1)
    status: AgentRunStatus = AgentRunStatus.CREATED
    parent_run_id: str | None = None
    model_id: str | None = None
    tokens_in: int = Field(default=0, ge=0)
    tokens_out: int = Field(default=0, ge=0)
    cost_usd: float = Field(default=0.0, ge=0)
    tool_calls: dict[str, Any] | None = None
    error_detail: dict[str, Any] | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class Task(BaseDocument):
    """Task entity (docs/plan/28 section 2.4) with embedded approval + estimate."""

    collection = "tasks"

    project_id: str = Field(min_length=1)
    type: str = Field(min_length=1, max_length=256)
    title: str = Field(min_length=1, max_length=1024)
    description: str | None = None
    priority: TaskPriority = TaskPriority.MEDIUM
    status: TaskStatus = TaskStatus.CREATED
    parent_task_id: str | None = None
    assigned_agent_id: str | None = None
    reviewer_agent_id: str | None = None
    dependencies: list[str] = Field(default_factory=list)
    inputs: list[str] = Field(default_factory=list)
    expected_outputs: list[str] = Field(default_factory=list)
    approval: dict[str, Any] | None = None
    estimate: dict[str, Any] | None = None
    retry_count: int = Field(default=0, ge=0)
    failure_reason: str | None = None
    write_scope: str | None = None
    cost_usd: float = Field(default=0.0, ge=0)
    started_at: datetime | None = None
    completed_at: datetime | None = None


class Workflow(BaseDocument):
    """Registered workflow definition (docs/plan/07 §2).

    The execution engine (a later phase) reads ``steps`` + ``entry``;
    ``workflow_runs.workflow_id`` refers to a definition by its stable
    ``workflow_id`` (not the document ``id``), matching plan 28 §2.6.
    """

    collection = "workflows"

    workflow_id: str = Field(min_length=1, max_length=256)
    version: int = Field(default=1, ge=1)
    name: str = Field(min_length=1, max_length=512)
    description: str | None = None
    entry: str | None = Field(default=None, max_length=256)
    steps: list[dict[str, Any]] = Field(default_factory=list)
    status: WorkflowStatus = WorkflowStatus.DRAFT


class WorkflowRun(BaseDocument):
    """Workflow execution state (docs/plan/28 section 2.6).

    ``workflow_id`` is the *definition* id (docs/plan/07) so a run stays
    addressable even as the definition document is re-versioned.
    """

    collection = "workflow_runs"

    project_id: str = Field(min_length=1)
    workflow_id: str = Field(min_length=1, max_length=256)
    status: WorkflowRunStatus = WorkflowRunStatus.CREATED
    current_step_stack: list[str] = Field(default_factory=list)
    step_results: dict[str, Any] | None = None


class TaskRun(BaseDocument):
    """One execution attempt (lease) of a task - docs/plan/08 §4 worker model.

    ``agent_run_id`` links the attempt to the concrete agent run that performed
    it; ``attempt`` increments per retry and is unique per task.
    """

    collection = "task_runs"

    task_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    attempt: int = Field(default=1, ge=1)
    status: TaskRunStatus = TaskRunStatus.CREATED
    assigned_agent_id: str | None = None
    worker_id: str | None = None
    agent_run_id: str | None = None
    lease_expires_at: datetime | None = None
    error_detail: dict[str, Any] | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None

    @field_validator("task_id", "project_id")
    @classmethod
    def _ref_ids(cls, value: str, info: ValidationInfo) -> str:
        return validate_doc_id(value, field=f"{info.field_name}")


class Artifact(BaseDocument):
    """Artifact registry row pointing at object storage (docs/plan/28 section 2.5)."""

    collection = "artifacts"

    project_id: str = Field(min_length=1)
    name: str = Field(min_length=1, max_length=512)
    kind: str = Field(min_length=1, max_length=128)
    version: int = Field(default=1, ge=1)
    uri: str = Field(min_length=1, max_length=2048)
    hash: str | None = None
    producer_run_id: str | None = None
    status: ArtifactStatus = ArtifactStatus.DRAFT
    derived_from: list[str] = Field(default_factory=list)
    approvals: list[str] = Field(default_factory=list)
    meta: dict[str, Any] | None = None


class Message(BaseDocument):
    """Governed inter-agent / agent-human message (docs/plan/28 section 2.12)."""

    collection = "messages"

    project_id: str | None = None
    trace_id: str | None = None
    type: MessageType = MessageType.NOTIFY
    sender: str = Field(min_length=1, max_length=256)
    recipient: str = Field(min_length=1, max_length=256)
    payload: dict[str, Any] | None = None
    status: MessageStatus = MessageStatus.PENDING
    delivered_at: datetime | None = None


class Memory(BaseDocument):
    """Memory entry; no mutation (append-only) - docs/plan/28 section 2.8."""

    collection = "memories"

    kind: MemoryKind
    content: str = Field(min_length=1)
    project_id: str | None = None
    task_id: str | None = None
    source_run_id: str | None = None
    confidence: float | None = Field(default=None, gt=0, le=1)
    access_scope: str = "project"
    embedding: list[float] | None = None


class Approval(BaseDocument):
    """Approval gateway record (docs/plan/28 section 2.7)."""

    collection = "approvals"

    project_id: str = Field(min_length=1)
    task_id: str | None = None
    workflow_run_id: str | None = None
    tier: ApprovalTier = ApprovalTier.T2
    title: str = Field(min_length=1, max_length=512)
    description: str | None = None
    material: dict[str, Any] | None = None
    status: ApprovalStatus = ApprovalStatus.PENDING
    decision: dict[str, Any] | None = None
    decided_at: datetime | None = None


class Review(BaseDocument):
    """Code/artifact review record (docs/plan/28 section 2.12)."""

    collection = "reviews"

    task_id: str = Field(min_length=1)
    reviewer_agent_id: str | None = None
    verdict: ReviewVerdict = ReviewVerdict.REQUEST_CHANGES
    findings: list[dict[str, Any]] = Field(default_factory=list)
    confidence: float | None = Field(default=None, gt=0, le=1)
    comment: str | None = None


class ToolCall(BaseDocument):
    """Tool invocation audit row (docs/plan/28 section 2.12)."""

    collection = "tool_calls"

    run_id: str = Field(min_length=1)
    tool_id: str = Field(min_length=1, max_length=256)
    args: dict[str, Any] | None = None
    status: ToolCallStatus = ToolCallStatus.ALLOWED
    result_size_bytes: int | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class Model(BaseDocument):
    """Model registry (docs/plan/28 section 2.12)."""

    collection = "models"

    model_id: str = Field(min_length=1, max_length=256)
    provider: ModelProvider
    capability: dict[str, Any] | None = None
    cost_per_1k: dict[str, Any] | None = None
    latency_ms_est: int | None = None
    enabled: bool = True
    privacy_local: bool = False


class Event(BaseDocument):
    """Event stream + outbox in one collection (docs/plan/28 section 2.9).

    Immutable log entries written once; ``status`` doubles as the outbox
    delivery marker (``pending`` → ``processed`` | ``failed``).
    """

    collection = "events"

    type: str = Field(min_length=1, max_length=256)
    payload: dict[str, Any] | None = None
    project_id: str | None = None
    emitted_by: dict[str, Any] | None = None
    trace_id: str | None = None
    status: EventStatus = EventStatus.PENDING


class AuditLog(BaseDocument):
    """Audit trail entry (append-only) - docs/plan/28 section 2.10."""

    collection = "audit_logs"

    ts: datetime = Field(default_factory=utcnow)
    action: str = Field(min_length=1, max_length=256)
    subject: str | None = None
    project_id: str | None = None
    resource_type: str | None = None
    resource_id: str | None = None
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    trace_id: str | None = None
