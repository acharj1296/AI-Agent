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


class AgentStatus(StrEnum):
    """Lifecycle of an agent *definition* in the registry (docs/plan/04 §1).

    Distinct from ``AgentRunStatus`` (lifecycle of one execution).  States:
    ``registered`` (definition created) → ``active`` (eligible for assignment)
    → ``inactive`` (paused, not eligible) → ``disabled`` (blocked) →
    ``deprecated`` (superseded, terminal).
    """

    REGISTERED = "registered"
    ACTIVE = "active"
    INACTIVE = "inactive"
    DISABLED = "disabled"
    DEPRECATED = "deprecated"


class AgentRole(StrEnum):
    """Canonical agent roles (docs/plan/05 §9, condensed).

    Role is the *function* an agent performs (used for role lookups), distinct
    from ``department`` (its organizational group) and ``capabilities`` (what
    it can do).
    """

    ORCHESTRATOR = "orchestrator"
    PRODUCT_MANAGER = "product-manager"
    BUSINESS_ANALYST = "business-analyst"
    RESEARCHER = "researcher"
    ARCHITECT = "architect"
    DEVELOPER = "developer"
    CODE_REVIEWER = "code-reviewer"
    QA_ENGINEER = "qa-engineer"
    SECURITY_ENGINEER = "security-engineer"
    DEVOPS_ENGINEER = "devops-engineer"
    PROJECT_MANAGER = "project-manager"


class AgentDepartment(StrEnum):
    """Agent organizational groups (docs/plan/05 §1-8)."""

    EXECUTIVE = "executive"
    PRODUCT = "product"
    RESEARCH = "research"
    ARCHITECTURE = "architecture"
    DEVELOPMENT = "development"
    QUALITY = "quality"
    DEVOPS = "devops"
    MANAGEMENT = "management"


class AgentCapability(StrEnum):
    """Machine-readable capability catalog (docs/plan/04 §5, 05 §2-8).

    ``<area>.<verb>`` form so the future task orchestrator can answer "which
    agents can perform this task?" by matching capability ids directly.
    """

    # research
    RESEARCH_MARKET = "research.market"
    RESEARCH_COMPETITOR = "research.competitor"
    RESEARCH_TECHNICAL = "research.technical"
    # product
    PRODUCT_REQUIREMENTS = "product.requirements"
    PRODUCT_PRD = "product.prd"
    PRODUCT_PLANNING = "product.planning"
    # architecture
    ARCHITECTURE_SYSTEM = "architecture.system"
    ARCHITECTURE_DATABASE = "architecture.database"
    ARCHITECTURE_SECURITY = "architecture.security"
    ARCHITECTURE_DEVOPS = "architecture.devops"
    # development
    DEVELOPMENT_FRONTEND = "development.frontend"
    DEVELOPMENT_BACKEND = "development.backend"
    DEVELOPMENT_DATABASE = "development.database"
    DEVELOPMENT_API = "development.api"
    DEVELOPMENT_INTEGRATION = "development.integration"
    # quality
    TESTING_UNIT = "testing.unit"
    TESTING_INTEGRATION = "testing.integration"
    TESTING_E2E = "testing.e2e"
    QUALITY_ASSURANCE = "quality.assurance"
    CODE_REVIEW = "code.review"
    # security
    SECURITY_AUDIT = "security.audit"
    SECURITY_TESTING = "security.testing"
    # devops
    DEVOPS_CICD = "devops.cicd"
    DEVOPS_DEPLOYMENT = "devops.deployment"
    DEVOPS_INFRASTRUCTURE = "devops.infrastructure"
    DEVOPS_MONITORING = "devops.monitoring"
    # management
    MANAGEMENT_PROJECT = "management.project"
    MANAGEMENT_PROGRESS = "management.progress"
    MANAGEMENT_DECISION = "management.decision"
    # documentation
    DOCUMENTATION = "documentation"


class ToolPermissionLevel(StrEnum):
    """Cap on what a tool permission grants (docs/plan/36 §1 default-deny).

    ``none`` is the default ceiling for every agent; tools are then granted
    at or below this ceiling via ``allowed_tool_ids`` / per-tool levels.
    """

    NONE = "none"
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    ADMIN = "admin"


class EgressPolicy(StrEnum):
    """Network egress policy for an agent (docs/plan/36 §4, 04 §1)."""

    NONE = "none"
    ALLOWLIST = "allowlist"
    LOCALHOST = "localhost"


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
