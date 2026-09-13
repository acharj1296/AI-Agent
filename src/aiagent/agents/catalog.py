"""Agent catalogue: capability groupings, role maps, eligibility and policy.

* :data:`DEPARTMENT_CAPABILITIES` - canonical capability sets per department
  (from docs/plan/04 §5, 05).  Used as defaults when seeding and as the
  reference for validation of new definitions.
* :func:`requires_trusted` - least-privilege guardrail: configurations that
  would grant high-risk permissions (ADMIN tools, secret access, code
  execution, unrestricted egress, migration/push) may only be registered via
  the trusted path (system seed / admin-scoped), never by default.
* :class:`AgentEligibilityQuery` + :func:`is_eligible` - the registry-level
  foundation the future Task System consumes to answer "which agents can
  perform this task?".  No assignment happens here.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from aiagent.core.errors import PolicyViolationError
from aiagent.db.constants import (
    AgentCapability,
    AgentDepartment,
    AgentRole,
    AgentStatus,
    EgressPolicy,
    ToolPermissionLevel,
)
from aiagent.db.models import Agent, ToolSet

# ---------------------------------------------------------------------------
# Capability catalogue (docs/plan/04 §5 capability matrix, 05 §2-8)
# ---------------------------------------------------------------------------

DEPARTMENT_CAPABILITIES: dict[AgentDepartment, frozenset[AgentCapability]] = {
    AgentDepartment.EXECUTIVE: frozenset(
        {
            AgentCapability.MANAGEMENT_PROJECT,
            AgentCapability.MANAGEMENT_DECISION,
            AgentCapability.DOCUMENTATION,
        }
    ),
    AgentDepartment.PRODUCT: frozenset(
        {
            AgentCapability.PRODUCT_REQUIREMENTS,
            AgentCapability.PRODUCT_PRD,
            AgentCapability.PRODUCT_PLANNING,
            AgentCapability.DOCUMENTATION,
        }
    ),
    AgentDepartment.RESEARCH: frozenset(
        {
            AgentCapability.RESEARCH_MARKET,
            AgentCapability.RESEARCH_COMPETITOR,
            AgentCapability.RESEARCH_TECHNICAL,
            AgentCapability.DOCUMENTATION,
        }
    ),
    AgentDepartment.ARCHITECTURE: frozenset(
        {
            AgentCapability.ARCHITECTURE_SYSTEM,
            AgentCapability.ARCHITECTURE_DATABASE,
            AgentCapability.ARCHITECTURE_SECURITY,
            AgentCapability.ARCHITECTURE_DEVOPS,
            AgentCapability.DOCUMENTATION,
        }
    ),
    AgentDepartment.DEVELOPMENT: frozenset(
        {
            AgentCapability.DEVELOPMENT_FRONTEND,
            AgentCapability.DEVELOPMENT_BACKEND,
            AgentCapability.DEVELOPMENT_DATABASE,
            AgentCapability.DEVELOPMENT_API,
            AgentCapability.DEVELOPMENT_INTEGRATION,
        }
    ),
    AgentDepartment.QUALITY: frozenset(
        {
            AgentCapability.TESTING_UNIT,
            AgentCapability.TESTING_INTEGRATION,
            AgentCapability.TESTING_E2E,
            AgentCapability.QUALITY_ASSURANCE,
            AgentCapability.CODE_REVIEW,
            AgentCapability.SECURITY_TESTING,
        }
    ),
    AgentDepartment.DEVOPS: frozenset(
        {
            AgentCapability.DEVOPS_CICD,
            AgentCapability.DEVOPS_DEPLOYMENT,
            AgentCapability.DEVOPS_INFRASTRUCTURE,
            AgentCapability.DEVOPS_MONITORING,
            AgentCapability.SECURITY_AUDIT,
        }
    ),
    AgentDepartment.MANAGEMENT: frozenset(
        {
            AgentCapability.MANAGEMENT_PROJECT,
            AgentCapability.MANAGEMENT_PROGRESS,
            AgentCapability.MANAGEMENT_DECISION,
            AgentCapability.DOCUMENTATION,
        }
    ),
}

#: Closest capability for a task ``type`` - the registry-level hint the task
#: system maps into a :class:`AgentEligibilityQuery` (docs/plan/08 §3).
TASK_TYPE_CAPABILITY: dict[str, AgentCapability] = {
    "research.market": AgentCapability.RESEARCH_MARKET,
    "research.competitor": AgentCapability.RESEARCH_COMPETITOR,
    "research.technical": AgentCapability.RESEARCH_TECHNICAL,
    "analysis": AgentCapability.RESEARCH_TECHNICAL,
    "prd": AgentCapability.PRODUCT_PRD,
    "requirements": AgentCapability.PRODUCT_REQUIREMENTS,
    "architecture": AgentCapability.ARCHITECTURE_SYSTEM,
    "database_design": AgentCapability.ARCHITECTURE_DATABASE,
    "frontend": AgentCapability.DEVELOPMENT_FRONTEND,
    "backend": AgentCapability.DEVELOPMENT_BACKEND,
    "api": AgentCapability.DEVELOPMENT_API,
    "database_dev": AgentCapability.DEVELOPMENT_DATABASE,
    "integration": AgentCapability.DEVELOPMENT_INTEGRATION,
    "unit_test": AgentCapability.TESTING_UNIT,
    "integration_test": AgentCapability.TESTING_INTEGRATION,
    "e2e_test": AgentCapability.TESTING_E2E,
    "code_review": AgentCapability.CODE_REVIEW,
    "qa": AgentCapability.QUALITY_ASSURANCE,
    "security_audit": AgentCapability.SECURITY_AUDIT,
    "deploy": AgentCapability.DEVOPS_DEPLOYMENT,
    "cicd": AgentCapability.DEVOPS_CICD,
    "infra": AgentCapability.DEVOPS_INFRASTRUCTURE,
    "documentation": AgentCapability.DOCUMENTATION,
    "planning": AgentCapability.PRODUCT_PLANNING,
}

# ---------------------------------------------------------------------------
# Least-privilege policy (docs/plan/36 §1, 39)
# ---------------------------------------------------------------------------

_UNRESTRICTED_WRITE_ROOTS = {"/", "/*", "~", "."}


def _tool_set_is_admin(tools: ToolSet | None) -> bool:
    if tools is None:
        return False
    if tools.default_level == ToolPermissionLevel.ADMIN:
        return True
    return any(lvl == ToolPermissionLevel.ADMIN for lvl in tools.tool_levels.values())


def requires_trusted(agent: Agent) -> bool:
    """True when the agent's configuration grants any high-risk permission.

    High-risk = ADMIN tool level, any secret access, code execution,
    unrestricted filesystem write root, database migration, merge push, or
    unrestricted network egress.  Default-deny: none of these are granted
    unless the caller explicitly marks the registration ``trusted``.
    """
    permissions = agent.permissions
    fs = permissions.filesystem if permissions else None
    network = permissions.network if permissions else None
    database = permissions.database if permissions else None
    code_exec = permissions.code_execution if permissions else None
    repository = permissions.repository if permissions else None
    secrets = permissions.secrets if permissions else None

    if _tool_set_is_admin(agent.tools):
        return True
    if secrets is not None and secrets.allowed_secret_names:
        return True
    if code_exec is not None and code_exec.allowed:
        return True
    if database is not None and database.can_migrate:
        return True
    if repository is not None and repository.can_push:
        return True
    if fs is not None and (fs.write_root or "") in _UNRESTRICTED_WRITE_ROOTS:
        return True
    if network is not None and network.egress not in (EgressPolicy.NONE, EgressPolicy.LOCALHOST):
        if not network.allow_hosts:
            return True
    return False


def assert_not_high_risk(agent: Agent) -> None:
    """Reject configurations that need elevation unless explicitly trusted."""
    if requires_trusted(agent):
        raise PolicyViolationError(
            "agent configuration requests high-risk permissions (ADMIN tools, "
            "secrets, unrestricted filesystem, unrestricted egress, code "
            "execution, migration or push) and requires explicit elevation"
        )


# ---------------------------------------------------------------------------
# Task eligibility foundation (registry level only)
# ---------------------------------------------------------------------------


class AgentEligibilityQuery(BaseModel):
    """Spec an agent must satisfy to be eligible for a task.

    Consumed by :meth:`aiagent.agents.services.AgentRegistryService.find_eligible`.
    Registry-level matching only - actual task assignment is a later step.
    """

    model_config = ConfigDict(extra="forbid")

    required_capabilities: list[AgentCapability] = Field(default_factory=list)
    departments: list[AgentDepartment] = Field(default_factory=list)
    roles: list[AgentRole] = Field(default_factory=list)
    required_tool_ids: list[str] = Field(default_factory=list)
    requires_write_filesystem: bool = False
    requires_code_execution: bool = False
    requires_network: bool = False
    min_autonomy_level: int = Field(default=0, ge=0, le=5)
    status: AgentStatus = AgentStatus.ACTIVE


def is_eligible(agent: Agent, query: AgentEligibilityQuery) -> bool:
    """Can *agent* (per its *definition*) satisfy *query*? (default-deny)."""
    if agent.status != query.status:
        return False
    if query.required_capabilities and not all(
        agent.has_capability(cap) for cap in query.required_capabilities
    ):
        return False
    if query.departments and agent.department not in query.departments:
        return False
    if query.roles and agent.role not in query.roles:
        return False
    if query.required_tool_ids and not all(
        agent.can_use_tool(tool_id) for tool_id in query.required_tool_ids
    ):
        return False

    permissions = agent.permissions
    if query.requires_write_filesystem:
        fs = permissions.filesystem if permissions else None
        if fs is None or not fs.write_root:
            return False
    if query.requires_code_execution:
        code_exec = permissions.code_execution if permissions else None
        if code_exec is None or not code_exec.allowed:
            return False
    if query.requires_network:
        network = permissions.network if permissions else None
        if network is None or network.egress == EgressPolicy.NONE:
            return False

    autonomy = agent.autonomy
    if (autonomy.level if autonomy else 0) < query.min_autonomy_level:
        return False
    return True
