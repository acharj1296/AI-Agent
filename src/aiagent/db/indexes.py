"""MongoDB collections and index initialization.

MVP collections (see `docs/plan/MONGODB_DESIGN.md` for the design; STEP 3 in
`docs/plan/STEP3_DOMAIN_MODELS.md` adds ``task_runs`` and ``workflows``):
identity (`organizations`, `users`), project state (`projects`), registry
(`agents`, `models`, `workflows`), execution (`agent_runs`, `tasks`,
`task_runs`, `workflow_runs`, `tool_calls`), artifacts (`artifacts`),
communication (`messages`, `reviews`, `approvals`), memory (`memories`), and
observability (`events`, `audit_logs`).

Deferred to later phases: `providers`, `knowledge`, `deployments`,
`environments`, `incidents`, `test_runs`.

Every index below exists to serve a documented query pattern; there are no
"just in case" indexes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase


@dataclass(frozen=True)
class IndexSpec:
    """A single index.

    * ``collection``: target collection
    * ``keys``: ``{field: ASC/DESC}`` mapping
    * ``name``: stable, deterministic index name (standard convention
      ``uq_`` unique / ``ix_`` regular)
    * ``unique``: enforce uniqueness at the database level
    * ``reason``: why the index exists (kept for documentation/audit)
    """

    collection: str
    keys: dict[str, int]
    name: str
    unique: bool = False
    reason: str = ""
    opts: dict[str, Any] = field(default_factory=dict)


MVP_COLLECTIONS: tuple[str, ...] = (
    "organizations",
    "users",
    "projects",
    "agents",
    "agent_runs",
    "tasks",
    "task_runs",
    "workflow_runs",
    "workflows",
    "artifacts",
    "messages",
    "memories",
    "approvals",
    "reviews",
    "tool_calls",
    "models",
    "events",
    "audit_logs",
)

INDEXES: tuple[IndexSpec, ...] = (
    # identity
    IndexSpec(
        "users",
        {"email": 1},
        "uq_users_email",
        unique=True,
        reason="sign-in / unique account lookup",
    ),
    IndexSpec("users", {"org_id": 1}, "ix_users_org_id", reason="list users of an organization"),
    # project state
    IndexSpec(
        "projects",
        {"org_id": 1, "status": 1},
        "ix_projects_org_status",
        reason="org project list filtered by status",
    ),
    IndexSpec(
        "projects",
        {"org_id": 1, "created_at": -1},
        "ix_projects_org_created",
        reason="newest-project-first listing",
    ),
    IndexSpec(
        "projects",
        {"status": 1, "stage": 1},
        "ix_projects_status_stage",
        reason="dashboard/funnel by status+stage",
    ),
    # agent + model registry
    IndexSpec(
        "agents",
        {"agent_id": 1},
        "uq_agents_agent_id",
        unique=True,
        reason="agents are addressed by stable agent_id",
    ),
    IndexSpec(
        "agents",
        {"slug": 1},
        "uq_agents_slug",
        unique=True,
        reason="registry resolves agents by unique human/URL slug",
    ),
    IndexSpec(
        "agents",
        {"status": 1, "department": 1},
        "ix_agents_status_department",
        reason="find active agents by department (registry lookup)",
    ),
    IndexSpec(
        "agents",
        {"status": 1, "role": 1},
        "ix_agents_status_role",
        reason="find active agents by role (registry lookup)",
    ),
    IndexSpec(
        "agents",
        {"status": 1, "capabilities": 1},
        "ix_agents_status_capability",
        reason="find active agents by capability (task eligibility)",
    ),
    IndexSpec(
        "models",
        {"model_id": 1},
        "uq_models_model_id",
        unique=True,
        reason="model registry key is model_id",
    ),
    IndexSpec(
        "models",
        {"provider": 1, "enabled": 1},
        "ix_models_provider_enabled",
        reason="model-router provider lookups",
    ),
    # agent runs
    IndexSpec(
        "agent_runs",
        {"task_id": 1, "status": 1},
        "ix_agent_runs_task_status",
        reason="run status per task",
    ),
    IndexSpec(
        "agent_runs",
        {"agent_id": 1, "status": 1},
        "ix_agent_runs_agent_status",
        reason="latest run per agent",
    ),
    IndexSpec(
        "agent_runs",
        {"project_id": 1, "created_at": -1},
        "ix_agent_runs_project_created",
        reason="audit/observability listing",
    ),
    IndexSpec(
        "agent_runs",
        {"agent_id": 1, "task_id": 1, "attempt": -1},
        "ix_agent_runs_agent_task_attempt",
        reason="per-agent/task attempt numbering for the runtime (STEP 5)",
    ),
    # tasks
    IndexSpec(
        "tasks",
        {"project_id": 1, "status": 1},
        "ix_tasks_project_status",
        reason="task board per project by status",
    ),
    IndexSpec(
        "tasks",
        {"status": 1, "priority": 1, "created_at": 1},
        "ix_tasks_status_priority",
        reason="worker queue pull order",
    ),
    IndexSpec(
        "tasks",
        {"project_id": 1, "parent_task_id": 1},
        "ix_tasks_project_parent",
        reason="sub-task tree traversal",
    ),
    # task runs (per-attempt lease records; docs/plan/08 §4)
    IndexSpec(
        "task_runs",
        {"task_id": 1, "attempt": 1},
        "uq_task_runs_task_attempt",
        unique=True,
        reason="one execution attempt per task - attempts are serialized",
    ),
    IndexSpec(
        "task_runs",
        {"status": 1, "created_at": 1},
        "ix_task_runs_status_created",
        reason="worker pooling: reclaim stale leases by status/age",
    ),
    IndexSpec(
        "task_runs",
        {"project_id": 1, "created_at": -1},
        "ix_task_runs_project_created",
        reason="audit/observability listing per project",
    ),
    # workflow runs
    IndexSpec(
        "workflow_runs",
        {"project_id": 1, "status": 1},
        "ix_workflow_runs_project_status",
        reason="active workflow per project",
    ),
    IndexSpec(
        "workflow_runs",
        {"project_id": 1, "created_at": -1},
        "ix_workflow_runs_project_created",
        reason="workflow history listing",
    ),
    # workflow definitions (docs/plan/07)
    IndexSpec(
        "workflows",
        {"workflow_id": 1, "version": -1},
        "uq_workflows_id_version",
        unique=True,
        reason="versioned workflow definitions - one document per (id, version)",
    ),
    IndexSpec(
        "workflows",
        {"status": 1, "created_at": -1},
        "ix_workflows_status_created",
        reason="active-definition registry listing",
    ),
    # artifacts
    IndexSpec(
        "artifacts",
        {"project_id": 1, "name": 1, "version": -1},
        "uq_artifacts_project_name_version",
        unique=True,
        reason="one version per (project, name) - docs/plan/28 unique constraint",
    ),
    IndexSpec(
        "artifacts",
        {"project_id": 1, "kind": 1},
        "ix_artifacts_project_kind",
        reason="artifact browser by kind",
    ),
    # communication
    IndexSpec(
        "messages",
        {"project_id": 1, "created_at": 1},
        "ix_messages_project_created",
        reason="conversation timeline",
    ),
    IndexSpec(
        "messages",
        {"recipient": 1, "status": 1},
        "ix_messages_recipient_status",
        reason="outbox-like delivery poll",
    ),
    IndexSpec("reviews", {"task_id": 1}, "ix_reviews_task", reason="review history per task"),
    # approvals
    IndexSpec(
        "approvals",
        {"project_id": 1, "status": 1},
        "ix_approvals_project_status",
        reason="pending approvals per project",
    ),
    IndexSpec(
        "approvals",
        {"status": 1, "created_at": 1},
        "ix_approvals_status_created",
        reason="approval queue ordered by age",
    ),
    # memories
    IndexSpec(
        "memories",
        {"project_id": 1, "kind": 1},
        "ix_memories_project_kind",
        reason="context assembly per project layer",
    ),
    IndexSpec("memories", {"task_id": 1}, "ix_memories_task", reason="task-scoped memory lookup"),
    # tool calls
    IndexSpec(
        "tool_calls",
        {"run_id": 1, "started_at": 1},
        "ix_tool_calls_run_started",
        reason="tool audit trail per run",
    ),
    IndexSpec("tool_calls", {"status": 1}, "ix_tool_calls_status", reason="denied/error triage"),
    # observability / audit
    IndexSpec(
        "events",
        {"project_id": 1, "created_at": -1},
        "ix_events_project_created",
        reason="event history per project",
    ),
    IndexSpec(
        "events",
        {"type": 1, "created_at": -1},
        "ix_events_type_created",
        reason="event-type timeline",
    ),
    IndexSpec(
        "events",
        {"status": 1, "created_at": 1},
        "ix_events_status_created",
        reason="outbox worker 'next pending' pull",
    ),
    IndexSpec("audit_logs", {"ts": -1}, "ix_audit_logs_ts", reason="time-ordered audit scan"),
    IndexSpec(
        "audit_logs",
        {"project_id": 1, "ts": -1},
        "ix_audit_logs_project_ts",
        reason="per-project audit browse",
    ),
)


async def ensure_collections_and_indexes(db: AsyncIOMotorDatabase) -> None:
    """Create the MVP collections (if absent) and their indexes (idempotent).

    Safe to run on every startup: ``create_collection`` and ``create_index``
    are no-ops when the target already exists.
    """
    existing = await db.list_collection_names()
    for name in MVP_COLLECTIONS:
        if name not in existing:
            await db.create_collection(name)

    for spec in INDEXES:
        await db[spec.collection].create_index(
            list(spec.keys.items()), name=spec.name, unique=spec.unique, **spec.opts
        )
