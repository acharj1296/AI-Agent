"""Controlled status/type enums used by the MongoDB document models.

Values mirror `docs/plan/28_DATABASE_DESIGN.md`; string values are stored
verbatim so historical documents keep stable semantics.
"""

from __future__ import annotations

from enum import StrEnum


class UserRole(StrEnum):
    ADMIN = "admin"
    REVIEWER = "reviewer"
    OBSERVER = "observer"


class ProjectStage(StrEnum):
    """Project lifecycle stage (docs/plan/13). Advanced only by the orchestrator."""

    IDEA = "idea"
    INTAKE = "intake"
    RESEARCH = "research"
    VALIDATION = "validation"
    PRD = "prd"
    ARCHITECTURE = "architecture"
    ROADMAP = "roadmap"
    TASK_GENERATION = "task_generation"
    DEVELOPMENT = "development"
    QA = "qa"
    SECURITY = "security"
    DEPLOYMENT = "deployment"
    MONITORING = "monitoring"
    MAINTENANCE = "maintenance"
    IMPROVEMENT = "improvement"


class ProjectStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TaskPriority(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TaskStatus(StrEnum):
    CREATED = "created"
    QUEUED = "queued"
    READY = "ready"
    ASSIGNED = "assigned"
    RUNNING = "running"
    REVIEW = "review"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


class AgentRunStatus(StrEnum):
    CREATED = "created"
    READY = "ready"
    CLAIMED = "claimed"
    RUNNING = "running"
    VALIDATING = "validating"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    ESCALATED = "escalated"
    PAUSED = "paused"
    CANCELLED = "cancelled"


class WorkflowRunStatus(StrEnum):
    """Workflow_run lifecycle. ``created`` marks a recorded run the engine has
    not started executing yet (STEP 3); the engine advances to ``running``."""

    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskRunStatus(StrEnum):
    """Per-attempt execution state of a task (worker lease model, docs/plan/08 §4)."""

    CREATED = "created"
    QUEUED = "queued"
    CLAIMED = "claimed"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class WorkflowStatus(StrEnum):
    """Lifecycle of a registered workflow definition (docs/plan/07)."""

    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class ApprovalTier(StrEnum):
    T0 = "t0"
    T1 = "t1"
    T2 = "t2"
    T3 = "t3"


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    OVERRIDDEN = "overridden"
    CANCELLED = "cancelled"


class ArtifactStatus(StrEnum):
    DRAFT = "draft"
    FINAL = "final"
    SUPERSEDED = "superseded"
    ARCHIVED = "archived"


class MessageType(StrEnum):
    INFO_REQUEST = "info.request"
    INFO_RESPONSE = "info.response"
    APPROVAL_PACKET = "approval.packet"
    NOTIFY = "notify"


class MessageStatus(StrEnum):
    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"


class ReviewVerdict(StrEnum):
    APPROVE = "approve"
    REQUEST_CHANGES = "request_changes"
    BLOCK = "block"


class ToolCallStatus(StrEnum):
    ALLOWED = "allowed"
    DENIED = "denied"
    OK = "ok"
    ERROR = "error"
    TIMEOUT = "timeout"


class ModelProvider(StrEnum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    OLLAMA = "ollama"
    VLLM = "vllm"


class MemoryKind(StrEnum):
    PROJECT = "project"
    TASK = "task"
    ORG = "org"
    AGENT_LONGTERM = "agent_longterm"
    CONVERSATION = "conversation"
    EPISODE = "episode"


class EventStatus(StrEnum):
    """Dual-purpose stream/outbox status (docs/plan/28 section 2.9)."""

    PENDING = "pending"
    PROCESSED = "processed"
    FAILED = "failed"
