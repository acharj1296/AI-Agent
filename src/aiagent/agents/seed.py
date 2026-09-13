"""Idempotent seeding of the MVP system agents (docs/plan/05, 33 §2).

Run explicitly via ``python -m aiagent.agents`` (or
:meth:`AgentRegistryService.run_seed`) - **not** on every application start,
so the registry does not override operator choices unexpectedly.

Idempotency contract:

* look up by ``slug`` and by ``agent_id``;
* if the agent already exists it is **skipped** (never duplicated, never
  overwrites a manual configuration);
* rerunning the seed is a no-op that returns the previously created agents.

Only the MVP task-flow agents from docs/plan/33 §2 exist (orchestrator, PM,
system architect, backend + frontend developers, code reviewer, QA lead, test
automation).  No unnecessary agents are created.
"""

from __future__ import annotations

from typing import Any

from aiagent.db.constants import (
    AgentCapability,
    AgentDepartment,
    AgentRole,
    AgentStatus,
    ApprovalTier,
    EgressPolicy,
    ToolPermissionLevel,
)
from aiagent.db.models import Agent

# ---------------------------------------------------------------------------
# MVP system agent definitions (docs/plan/05 §1-8, 33 §2)
# ---------------------------------------------------------------------------

SYSTEM_AGENTS: list[dict[str, Any]] = [
    {
        "agent_id": "ceo_orchestrator",
        "slug": "orchestrator",
        "name": "Orchestrator",
        "description": "CEO-level agent: owns the pipeline, stage gates and "
        "dispatch; never edits user code (docs/plan/05 §1).",
        "role": AgentRole.ORCHESTRATOR,
        "department": AgentDepartment.EXECUTIVE,
        "capabilities": [
            AgentCapability.MANAGEMENT_PROJECT,
            AgentCapability.MANAGEMENT_DECISION,
            AgentCapability.DOCUMENTATION,
        ],
        "system_prompt_ref": "system/orchestrator/v1",
        "tools": {
            "allowed_tool_ids": [
                "read_project_state",
                "read_artifacts",
                "list_tasks",
                "request_approval",
                "escalate_to_human",
            ],
            "default_level": ToolPermissionLevel.READ,
        },
        "permissions": {
            "filesystem": {"read_root": "artifacts/"},
            "network": {"egress": EgressPolicy.NONE},
            "secrets": {},
        },
        "autonomy": {"level": 2, "approval_tiers": [ApprovalTier.T3]},
    },
    {
        "agent_id": "pm_product_manager",
        "slug": "product-manager",
        "name": "Product Manager",
        "description": "Turns research + intake into a PRD, roadmap and "
        "prioritized story backlog (docs/plan/05 §2.1).",
        "role": AgentRole.PRODUCT_MANAGER,
        "department": AgentDepartment.PRODUCT,
        "capabilities": [
            AgentCapability.PRODUCT_REQUIREMENTS,
            AgentCapability.PRODUCT_PRD,
            AgentCapability.PRODUCT_PLANNING,
            AgentCapability.DOCUMENTATION,
        ],
        "system_prompt_ref": "system/product-manager/v1",
        "tools": {
            "allowed_tool_ids": ["read_project_state", "read_artifacts", "write_artifacts"],
            "default_level": ToolPermissionLevel.WRITE,
        },
        "permissions": {
            "filesystem": {"read_root": "artifacts/", "write_root": "artifacts/"},
            "network": {"egress": EgressPolicy.NONE},
            "secrets": {},
        },
        "autonomy": {"level": 2, "approval_tiers": [ApprovalTier.T2, ApprovalTier.T3]},
    },
    {
        "agent_id": "arch_system",
        "slug": "system-architect",
        "name": "System Architect",
        "description": "High-level system design from the PRD: architecture, "
        "C4 diagrams, ADRs (docs/plan/05 §4.1).",
        "role": AgentRole.ARCHITECT,
        "department": AgentDepartment.ARCHITECTURE,
        "capabilities": [
            AgentCapability.ARCHITECTURE_SYSTEM,
            AgentCapability.DOCUMENTATION,
        ],
        "system_prompt_ref": "system/system-architect/v1",
        "tools": {
            "allowed_tool_ids": ["read_project_state", "read_artifacts", "write_artifacts"],
            "default_level": ToolPermissionLevel.WRITE,
        },
        "permissions": {
            "filesystem": {"read_root": "artifacts/", "write_root": "artifacts/"},
            "network": {"egress": EgressPolicy.NONE},
            "secrets": {},
        },
        "autonomy": {"level": 2, "approval_tiers": [ApprovalTier.T2, ApprovalTier.T3]},
    },
    {
        "agent_id": "dev_backend",
        "slug": "backend-developer",
        "name": "Backend Developer",
        "description": "Implements backend features, business logic and "
        "services from assigned tasks (docs/plan/05 §5.1).",
        "role": AgentRole.DEVELOPER,
        "department": AgentDepartment.DEVELOPMENT,
        "capabilities": [
            AgentCapability.DEVELOPMENT_BACKEND,
            AgentCapability.DEVELOPMENT_API,
        ],
        "system_prompt_ref": "system/backend-developer/v1",
        "tools": {
            "allowed_tool_ids": [
                "read_file",
                "write_file",
                "list_dir",
                "run_terminal",
                "git_commit",
                "run_tests",
                "read_repo",
            ],
            "default_level": ToolPermissionLevel.EXECUTE,
            "tool_levels": {
                "git_commit": ToolPermissionLevel.EXECUTE,
                "run_terminal": ToolPermissionLevel.EXECUTE,
            },
        },
        "permissions": {
            "filesystem": {"read_root": "/workspace", "write_root": "/workspace"},
            "network": {"egress": EgressPolicy.NONE},
            "code_execution": {"allowed": True, "sandbox": "workspaces/default"},
            "repository": {"repositories": ["project_workspace"], "can_commit": True},
            "secrets": {},
        },
        "autonomy": {"level": 2, "approval_tiers": [ApprovalTier.T3]},
    },
    {
        "agent_id": "dev_frontend",
        "slug": "frontend-developer",
        "name": "Frontend Developer",
        "description": "Builds UI components, pages and API wiring " "(docs/plan/05 §5.2).",
        "role": AgentRole.DEVELOPER,
        "department": AgentDepartment.DEVELOPMENT,
        "capabilities": [AgentCapability.DEVELOPMENT_FRONTEND],
        "system_prompt_ref": "system/frontend-developer/v1",
        "tools": {
            "allowed_tool_ids": [
                "read_file",
                "write_file",
                "list_dir",
                "run_terminal",
                "git_commit",
                "run_tests",
                "read_repo",
            ],
            "default_level": ToolPermissionLevel.EXECUTE,
            "tool_levels": {"run_terminal": ToolPermissionLevel.EXECUTE},
        },
        "permissions": {
            "filesystem": {"read_root": "/workspace", "write_root": "/workspace"},
            "network": {"egress": EgressPolicy.NONE},
            "code_execution": {"allowed": True, "sandbox": "workspaces/default"},
            "repository": {"repositories": ["project_workspace"], "can_commit": True},
            "secrets": {},
        },
        "autonomy": {"level": 2, "approval_tiers": [ApprovalTier.T3]},
    },
    {
        "agent_id": "qa_code_reviewer",
        "slug": "code-reviewer",
        "name": "Code Reviewer",
        "description": "Reviews diffs for correctness, style, security and "
        "performance; produces structured reviews (docs/plan/05 §6.3).",
        "role": AgentRole.CODE_REVIEWER,
        "department": AgentDepartment.QUALITY,
        "capabilities": [
            AgentCapability.CODE_REVIEW,
            AgentCapability.SECURITY_TESTING,
        ],
        "system_prompt_ref": "system/code-reviewer/v1",
        "tools": {
            "allowed_tool_ids": ["read_file", "read_repo", "read_project_state", "read_artifacts"],
            "default_level": ToolPermissionLevel.READ,
        },
        "permissions": {
            "filesystem": {"read_root": "/workspace"},
            "network": {"egress": EgressPolicy.NONE},
            "secrets": {},
        },
        "autonomy": {"level": 2, "approval_tiers": [ApprovalTier.T3]},
    },
    {
        "agent_id": "qa_lead",
        "slug": "qa-lead",
        "name": "QA Lead",
        "description": "Test-plan authoring, coverage mapping to "
        "requirements, fix-loop coordination (docs/plan/05 §6.1).",
        "role": AgentRole.QA_ENGINEER,
        "department": AgentDepartment.QUALITY,
        "capabilities": [
            AgentCapability.QUALITY_ASSURANCE,
            AgentCapability.TESTING_UNIT,
            AgentCapability.TESTING_INTEGRATION,
            AgentCapability.TESTING_E2E,
        ],
        "system_prompt_ref": "system/qa-lead/v1",
        "tools": {
            "allowed_tool_ids": ["read_project_state", "read_artifacts", "write_artifacts"],
            "default_level": ToolPermissionLevel.WRITE,
        },
        "permissions": {
            "filesystem": {"read_root": "artifacts/", "write_root": "artifacts/"},
            "network": {"egress": EgressPolicy.NONE},
            "secrets": {},
        },
        "autonomy": {"level": 2, "approval_tiers": [ApprovalTier.T3]},
    },
    {
        "agent_id": "qa_test_automation",
        "slug": "test-automation",
        "name": "Test Automation",
        "description": "Writes unit/integration/E2E tests, runs suites and "
        "formats results (docs/plan/05 §6.2).",
        "role": AgentRole.QA_ENGINEER,
        "department": AgentDepartment.QUALITY,
        "capabilities": [
            AgentCapability.TESTING_UNIT,
            AgentCapability.TESTING_INTEGRATION,
            AgentCapability.TESTING_E2E,
        ],
        "system_prompt_ref": "system/test-automation/v1",
        "tools": {
            "allowed_tool_ids": [
                "read_file",
                "write_file",
                "list_dir",
                "run_terminal",
                "run_tests",
                "read_repo",
            ],
            "default_level": ToolPermissionLevel.EXECUTE,
            "tool_levels": {"run_tests": ToolPermissionLevel.EXECUTE},
        },
        "permissions": {
            "filesystem": {"read_root": "/workspace", "write_root": "/workspace/tests"},
            "network": {"egress": EgressPolicy.NONE},
            "code_execution": {"allowed": True, "sandbox": "workspaces/default"},
            "secrets": {},
        },
        "autonomy": {"level": 2, "approval_tiers": [ApprovalTier.T3]},
    },
]


async def seed_system_agents(registry) -> list[Agent]:
    """Create the MVP system agents; safe to run repeatedly (idempotent).

    Existing agents (by ``slug`` *or* ``agent_id``) are skipped so manual
    configuration is never overwritten.  Returns the agents present in the
    registry for the system set after the run.
    """
    created: list[Agent] = []
    for definition in SYSTEM_AGENTS:
        existing = await registry.find_any(definition["slug"], definition["agent_id"])
        if existing is not None:
            created.append(existing)
            continue
        agent = await registry.register_agent(
            agent_id=definition["agent_id"],
            name=definition["name"],
            slug=definition["slug"],
            description=definition.get("description"),
            role=definition["role"],
            department=definition["department"],
            status=AgentStatus.ACTIVE,
            version="1.0.0",
            capabilities=definition["capabilities"],
            system_prompt_ref=definition.get("system_prompt_ref"),
            model=definition.get("model"),
            tools=definition["tools"],
            permissions=definition["permissions"],
            autonomy=definition["autonomy"],
            trusted=True,
        )
        created.append(agent)
    return created
