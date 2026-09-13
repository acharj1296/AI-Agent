"""Unit tests for the Agent Registry layer (STEP 4).

These tests run entirely offline (no MongoDB) by exercising the domain model
validation, status-state-machine, capability/eligibility catalog, and the
least-privilege guardrail in isolation.
"""

from __future__ import annotations

from typing import Any

import pytest

from aiagent.agents.catalog import (
    AgentEligibilityQuery,
    is_eligible,
    requires_trusted,
)
from aiagent.agents.services import AgentRegistryService, _bump
from aiagent.agents.status import assert_transition
from aiagent.core.errors import InvalidStateError
from aiagent.db.constants import (
    AgentCapability,
    AgentDepartment,
    AgentRole,
    AgentStatus,
    EgressPolicy,
    ToolPermissionLevel,
)
from aiagent.db.models import Agent, ModelConfig, ToolSet

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _agent(
    *,
    agent_id: str = "test_agent",
    slug: str = "test-agent",
    role: AgentRole = AgentRole.DEVELOPER,
    department: AgentDepartment | None = AgentDepartment.DEVELOPMENT,
    status: AgentStatus = AgentStatus.ACTIVE,
    capabilities: list[AgentCapability] | None = None,
    tools: ToolSet | None = None,
    permissions: dict[str, Any] | None = None,
    autonomy_level: int = 0,
    trusted: bool = False,
) -> Agent:
    """Fast helper to build an ``Agent`` with sensible defaults."""
    from aiagent.db.models import AutonomyConfig, ResourcePermissions

    perm = ResourcePermissions.model_validate(permissions) if permissions else None
    auto = AutonomyConfig(level=autonomy_level) if autonomy_level else None
    return Agent(
        agent_id=agent_id,
        name=agent_id,
        slug=slug,
        role=role,
        department=department,
        status=status,
        version="1.0.0",
        capabilities=capabilities or [],
        tools=tools,
        permissions=perm,
        autonomy=auto,
    )


# ===================================================================
# 1.  Agent model validation
# ===================================================================


class TestAgentModelValidation:
    def test_valid_minimal_agent(self) -> None:
        agent = _agent()
        assert agent.agent_id == "test_agent"
        assert agent.slug == "test-agent"
        assert agent.status is AgentStatus.ACTIVE
        assert agent.version == "1.0.0"

    def test_slug_must_be_lowercase_hyphenated(self) -> None:
        with pytest.raises(ValueError, match="slug"):
            Agent(agent_id="a", name="a", slug="INVALID_SLUG!", version="1.0.0")

    def test_version_must_be_semver(self) -> None:
        with pytest.raises(ValueError, match="pattern"):
            Agent(agent_id="a", name="a", slug="a", version="1.0")

    def test_empty_agent_id_rejected(self) -> None:
        with pytest.raises(ValueError):
            Agent(agent_id="", name="x", slug="x", version="1.0.0")

    def test_empty_name_rejected(self) -> None:
        with pytest.raises(ValueError):
            Agent(agent_id="x", name="", slug="x", version="1.0.0")


# ===================================================================
# 2.  Tool permission level ranking
# ===================================================================


class TestToolPermissions:
    def test_read_agent_can_read_file(self) -> None:
        agent = _agent(tools=ToolSet(allowed_tool_ids=["read_file"]))
        assert agent.can_use_tool("read_file", level=ToolPermissionLevel.READ)

    def test_read_agent_cannot_write(self) -> None:
        agent = _agent(tools=ToolSet(allowed_tool_ids=["read_file"]))
        assert not agent.can_use_tool("read_file", level=ToolPermissionLevel.WRITE)

    def test_default_deny_for_unknown_tool(self) -> None:
        agent = _agent(tools=ToolSet(allowed_tool_ids=["read_file"]))
        assert not agent.can_use_tool("run_terminal", level=ToolPermissionLevel.READ)

    def test_execute_grant_implies_write_and_read(self) -> None:
        agent = _agent(
            tools=ToolSet(
                allowed_tool_ids=["run_tests"],
                tool_levels={"run_tests": ToolPermissionLevel.EXECUTE},
            )
        )
        assert agent.can_use_tool("run_tests", level=ToolPermissionLevel.READ)
        assert agent.can_use_tool("run_tests", level=ToolPermissionLevel.WRITE)
        assert agent.can_use_tool("run_tests", level=ToolPermissionLevel.EXECUTE)
        assert not agent.can_use_tool("run_tests", level=ToolPermissionLevel.ADMIN)

    def test_agent_with_no_tools_declined(self) -> None:
        agent = _agent()
        assert not agent.can_use_tool("read_file")


# ===================================================================
# 3.  Capability checks
# ===================================================================


class TestCapabilities:
    def test_has_capability(self) -> None:
        agent = _agent(capabilities=[AgentCapability.DEVELOPMENT_BACKEND])
        assert agent.has_capability(AgentCapability.DEVELOPMENT_BACKEND)
        assert not agent.has_capability(AgentCapability.DEVELOPMENT_FRONTEND)

    def test_has_capability_str(self) -> None:
        agent = _agent(capabilities=[AgentCapability.DEVELOPMENT_BACKEND])
        assert agent.has_capability("development.backend")


# ===================================================================
# 4.  Embedded config submodel construction
# ===================================================================


class TestConfigSubmodels:
    def test_model_config_with_provider_and_model(self) -> None:
        cfg = ModelConfig(provider="openai", model="gpt-4o")
        assert cfg.provider == "openai"
        assert cfg.model == "gpt-4o"

    def test_model_config_provider_requires_model(self) -> None:
        with pytest.raises(ValueError):
            ModelConfig(provider="openai")

    def test_model_config_no_provider_no_model_fine(self) -> None:
        cfg = ModelConfig()
        assert cfg.provider is None
        assert cfg.model is None

    def test_tool_set_level_for_known(self) -> None:
        ts = ToolSet(
            allowed_tool_ids=["run_tests"],
            default_level=ToolPermissionLevel.READ,
            tool_levels={"run_tests": ToolPermissionLevel.EXECUTE},
        )
        assert ts.level_for("run_tests") is ToolPermissionLevel.EXECUTE

    def test_tool_set_level_for_known_uses_default(self) -> None:
        ts = ToolSet(
            allowed_tool_ids=["read_file"],
            default_level=ToolPermissionLevel.READ,
        )
        assert ts.level_for("read_file") is ToolPermissionLevel.READ

    def test_tool_not_allowed_denied(self) -> None:
        ts = ToolSet(
            allowed_tool_ids=["read_file"],
            default_level=ToolPermissionLevel.READ,
        )
        assert ts.level_for("run_terminal") is ToolPermissionLevel.NONE


# ===================================================================
# 5.  Status state machine
# ===================================================================


class TestStatusStateMachine:
    @pytest.mark.parametrize(
        "current, next_status",
        [
            (AgentStatus.REGISTERED, AgentStatus.ACTIVE),
            (AgentStatus.ACTIVE, AgentStatus.INACTIVE),
            (AgentStatus.ACTIVE, AgentStatus.DISABLED),
            (AgentStatus.ACTIVE, AgentStatus.DEPRECATED),
            (AgentStatus.INACTIVE, AgentStatus.ACTIVE),
            (AgentStatus.INACTIVE, AgentStatus.DISABLED),
            (AgentStatus.INACTIVE, AgentStatus.DEPRECATED),
            (AgentStatus.DISABLED, AgentStatus.ACTIVE),
            (AgentStatus.DISABLED, AgentStatus.DEPRECATED),
        ],
    )
    def test_valid_transitions(self, current: AgentStatus, next_status: AgentStatus) -> None:
        assert_transition(current, next_status)

    @pytest.mark.parametrize(
        "current, next_status",
        [
            (AgentStatus.REGISTERED, AgentStatus.DISABLED),
            (AgentStatus.REGISTERED, AgentStatus.DEPRECATED),
            (AgentStatus.DISABLED, AgentStatus.INACTIVE),
            (AgentStatus.ACTIVE, AgentStatus.REGISTERED),
        ],
    )
    def test_invalid_transitions(self, current: AgentStatus, next_status: AgentStatus) -> None:
        with pytest.raises(InvalidStateError):
            assert_transition(current, next_status)

    def test_deprecated_is_terminal(self) -> None:
        for target in AgentStatus:
            if target is AgentStatus.DEPRECATED:
                continue
            with pytest.raises(InvalidStateError):
                assert_transition(AgentStatus.DEPRECATED, target)


# ===================================================================
# 6.  Least-privilege guardrail (requires_trusted / assert_not_high_risk)
# ===================================================================


class TestLeastPrivilegeGuardrail:
    def test_plain_agent_is_low_risk(self) -> None:
        agent = _agent(
            tools=ToolSet(allowed_tool_ids=["read_file"]),
            permissions={"filesystem": {"read_root": "docs/"}},
        )
        assert not requires_trusted(agent)

    def test_admin_tool_level_triggers(self) -> None:
        agent = _agent(
            tools=ToolSet(
                allowed_tool_ids=["run_terminal"],
                tool_levels={"run_terminal": ToolPermissionLevel.ADMIN},
            )
        )
        assert requires_trusted(agent)

    def test_code_execution_triggers(self) -> None:
        agent = _agent(permissions={"code_execution": {"allowed": True, "sandbox": "test"}})
        assert requires_trusted(agent)

    def test_unrestricted_write_root_triggers(self) -> None:
        agent = _agent(permissions={"filesystem": {"write_root": "/"}})
        assert requires_trusted(agent)

    def test_restricted_write_root_ok(self) -> None:
        agent = _agent(permissions={"filesystem": {"write_root": "/workspace"}})
        assert not requires_trusted(agent)

    def test_secrets_access_triggers(self) -> None:
        agent = _agent(permissions={"secrets": {"allowed_secret_names": ["api_key"]}})
        assert requires_trusted(agent)

    def test_database_migration_triggers(self) -> None:
        agent = _agent(permissions={"database": {"can_migrate": True}})
        assert requires_trusted(agent)

    def test_repository_push_triggers(self) -> None:
        agent = _agent(permissions={"repository": {"can_push": True}})
        assert requires_trusted(agent)


# ===================================================================
# 7.  Task eligibility foundation
# ===================================================================


class TestAgentEligibility:
    def test_eligible_agent_matches(self) -> None:
        agent = _agent(
            capabilities=[AgentCapability.DEVELOPMENT_BACKEND],
            autonomy_level=2,
            permissions={"filesystem": {"read_root": "/workspace", "write_root": "/workspace"}},
        )
        query = AgentEligibilityQuery(
            required_capabilities=[AgentCapability.DEVELOPMENT_BACKEND],
            requires_write_filesystem=True,
        )
        assert is_eligible(agent, query)

    def test_missing_capability_rejects(self) -> None:
        agent = _agent(capabilities=[AgentCapability.DEVELOPMENT_BACKEND])
        query = AgentEligibilityQuery(
            required_capabilities=[AgentCapability.DEVELOPMENT_FRONTEND],
        )
        assert not is_eligible(agent, query)

    def test_wrong_department_rejects(self) -> None:
        agent = _agent(department=AgentDepartment.DEVELOPMENT)
        query = AgentEligibilityQuery(departments=[AgentDepartment.QUALITY])
        assert not is_eligible(agent, query)

    def test_wrong_status_rejects(self) -> None:
        agent = _agent(status=AgentStatus.INACTIVE)
        query = AgentEligibilityQuery()
        assert not is_eligible(agent, query)

    def test_write_filesystem_needed_but_absent_rejects(self) -> None:
        agent = _agent(permissions={"filesystem": {"read_root": "docs/"}})
        query = AgentEligibilityQuery(requires_write_filesystem=True)
        assert not is_eligible(agent, query)

    def test_autonomy_level_too_low_rejects(self) -> None:
        agent = _agent(autonomy_level=1)
        query = AgentEligibilityQuery(min_autonomy_level=3)
        assert not is_eligible(agent, query)

    def test_code_execution_needed_but_absent_rejects(self) -> None:
        agent = _agent()
        query = AgentEligibilityQuery(requires_code_execution=True)
        assert not is_eligible(agent, query)

    def test_network_needed_but_egress_none_rejects(self) -> None:
        agent = _agent(
            permissions={"network": {"egress": EgressPolicy.NONE}},
        )
        query = AgentEligibilityQuery(requires_network=True)
        assert not is_eligible(agent, query)

    def test_network_needed_egress_allowlist_passes(self) -> None:
        agent = _agent(
            permissions={
                "network": {
                    "egress": EgressPolicy.ALLOWLIST,
                    "allow_hosts": ["api.example.com"],
                }
            },
        )
        query = AgentEligibilityQuery(requires_network=True)
        assert is_eligible(agent, query)


# ===================================================================
# 8.  Version helpers
# ===================================================================


class TestVersionHelpers:
    def test_bump_patch(self) -> None:
        assert _bump("1.0.0") == "1.0.1"
        assert _bump("2.3.9") == "2.3.10"
        assert _bump("0.0.0") == "0.0.1"

    def test_validated_version_allows_same_or_greater(self) -> None:
        assert AgentRegistryService._validated_version("1.0.1", "1.0.0") == "1.0.1"
        assert AgentRegistryService._validated_version("1.0.0", "1.0.0") == "1.0.0"

    def test_validated_version_rejects_downgrade(self) -> None:
        with pytest.raises(InvalidStateError, match="older"):
            AgentRegistryService._validated_version("0.9.0", "1.0.0")
