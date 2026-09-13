"""Integration tests for the STEP 4 Agent Registry.

Requires a reachable MongoDB (skipped otherwise); runs against the isolated
``aiagent_test`` database provided by the shared ``mongo_db`` fixture.
"""

from __future__ import annotations

import pytest

from aiagent.agents.catalog import AgentEligibilityQuery
from aiagent.core.errors import (
    ConflictError,
    InvalidStateError,
    NotFoundError,
    PolicyViolationError,
)
from aiagent.db.constants import (
    AgentCapability,
    AgentDepartment,
    AgentRole,
    AgentStatus,
)
from aiagent.db.models import Agent, ToolSet
from aiagent.services import build_service_layer

pytestmark = pytest.mark.integration


async def _register(
    layer,
    agent_id: str = "backend_agent",
    *,
    slug: str | None = None,
    name: str | None = None,
    department=None,
    status=None,
    trusted: bool = False,
    **kwargs,
) -> Agent:
    return await layer.agents.register_agent(
        agent_id=agent_id,
        slug=slug or agent_id.replace("_", "-"),
        name=name or agent_id,
        department=department,
        status=status,
        trusted=trusted,
        **kwargs,
    )


async def test_register_agent_persists_definition(mongo_db) -> None:
    layer = build_service_layer(mongo_db)

    agent = await _register(
        layer,
        "arch_system",
        slug="system-architect",
        name="System Architect",
        department=AgentDepartment.ARCHITECTURE,
        role=AgentRole.ARCHITECT,
        capabilities=[AgentCapability.ARCHITECTURE_SYSTEM],
    )

    assert agent.slug == "system-architect"
    assert agent.status is AgentStatus.REGISTERED
    assert agent.version == "1.0.0"

    raw = await mongo_db["agents"].find_one({"agent_id": "arch_system"})
    assert raw is not None
    assert raw["_id"] == agent.id
    assert raw["slug"] == "system-architect"
    assert (await mongo_db["events"].find_one({"type": "agent.created"})) is not None
    assert await mongo_db["audit_logs"].find_one({"action": "agent.register"})


async def test_register_duplicate_agent_id_conflicts(mongo_db) -> None:
    layer = build_service_layer(mongo_db)
    await _register(layer, "dev_backend", slug="backend-developer")

    with pytest.raises(ConflictError):
        await _register(layer, "dev_backend", slug="other-slug")


async def test_register_duplicate_slug_conflicts(mongo_db) -> None:
    layer = build_service_layer(mongo_db)
    await _register(layer, "dev_backend", slug="backend-developer")

    with pytest.raises(ConflictError):
        await _register(layer, "dev_frontend", slug="backend-developer")


async def test_slug_defaults_from_agent_id(mongo_db) -> None:
    layer = build_service_layer(mongo_db)
    agent = await layer.agents.register_agent(agent_id="dev_backend")
    assert agent.slug == "dev-backend"


async def test_registered_status_only_registered_or_active(mongo_db) -> None:
    layer = build_service_layer(mongo_db)
    with pytest.raises(PolicyViolationError):
        await _register(layer, "bad", status=AgentStatus.DISABLED)


async def test_lookups_by_docid_slug_and_agentid(mongo_db) -> None:
    layer = build_service_layer(mongo_db)
    agent = await _register(layer, "pm", slug="product-manager")

    assert (await layer.agents.get_agent(agent.id)).agent_id == "pm"
    assert (await layer.agents.find_agent("pm")).id == agent.id
    assert (await layer.agents.find_by_slug("product-manager")).id == agent.id


async def test_update_name_and_version_bump_with_audit(mongo_db) -> None:
    layer = build_service_layer(mongo_db)
    agent = await _register(layer, "dev_backend", name="Backend Dev", config={"k": "v"})

    updated = await layer.agents.update_agent(agent.id, name="Backend Dev v2", config={"k": "v2"})
    assert updated.name == "Backend Dev v2"
    assert updated.version == "1.0.1"

    audit = await mongo_db["audit_logs"].find_one(
        {"action": "agent.update", "resource_id": agent.id}
    )
    assert audit["before"]["name"] == "Backend Dev"
    assert audit["after"]["name"] == "Backend Dev v2"
    assert (await mongo_db["events"].find_one({"type": "agent.updated"})) is not None


async def test_update_config_block_emits_aspect_event(mongo_db) -> None:
    layer = build_service_layer(mongo_db)
    agent = await _register(
        layer,
        "auto_agent",
        permissions={"filesystem": {"read_root": "docs/"}},
    )
    await layer.agents.update_agent(agent.id, permissions={"filesystem": {"read_root": "/"}})
    assert (await mongo_db["events"].find_one({"type": "agent.permissions_changed"})) is not None


async def test_update_rejects_status_flag(mongo_db) -> None:
    layer = build_service_layer(mongo_db)
    agent = await _register(layer, "x")
    with pytest.raises(InvalidStateError):
        await layer.agents.update_agent(agent.id, status=AgentStatus.ACTIVE)


async def test_update_version_downgrade_rejected(mongo_db) -> None:
    layer = build_service_layer(mongo_db)
    agent = await _register(layer, "y")
    with pytest.raises(InvalidStateError):
        await layer.agents.update_agent(agent.id, version="0.9.0")


async def test_update_slug_collision_rejected(mongo_db) -> None:
    layer = build_service_layer(mongo_db)
    await _register(layer, "a", slug="taken")
    other = await _register(layer, "b")

    with pytest.raises(ConflictError):
        await layer.agents.update_agent(other.id, slug="taken")


async def test_update_to_high_risk_without_trust_rejected(mongo_db) -> None:
    layer = build_service_layer(mongo_db)
    agent = await _register(layer, "sec")

    with pytest.raises(PolicyViolationError):
        await layer.agents.update_agent(agent.id, permissions={"code_execution": {"allowed": True}})


async def test_update_unknown_agent_not_found(mongo_db) -> None:
    layer = build_service_layer(mongo_db)
    with pytest.raises(NotFoundError):
        await layer.agents.update_agent("0" * 32, name="nope")


async def test_lifecycle_transitions(mongo_db) -> None:
    layer = build_service_layer(mongo_db)
    agent = await _register(layer, "life", status=AgentStatus.REGISTERED)

    enabled = await layer.agents.enable_agent(agent.agent_id)
    assert enabled.status is AgentStatus.ACTIVE

    disabled = await layer.agents.disable_agent(agent.agent_id)
    assert disabled.status is AgentStatus.DISABLED

    reenabled = await layer.agents.enable_agent(agent.agent_id)
    assert reenabled.status is AgentStatus.ACTIVE

    deprecated = await layer.agents.deprecate_agent(agent.agent_id)
    assert deprecated.status is AgentStatus.DEPRECATED

    assert (await mongo_db["events"].find_one({"type": "agent.enabled"})) is not None
    assert (await mongo_db["events"].find_one({"type": "agent.disabled"})) is not None
    assert (await mongo_db["events"].find_one({"type": "agent.deprecated"})) is not None


async def test_invalid_status_transition_rejected(mongo_db) -> None:
    layer = build_service_layer(mongo_db)
    agent = await _register(layer, "bad_state", status=AgentStatus.REGISTERED)

    with pytest.raises(InvalidStateError):
        await layer.agents.disable_agent(agent.agent_id)


async def test_deprecated_is_terminal(mongo_db) -> None:
    layer = build_service_layer(mongo_db)
    agent = await _register(layer, "term", status=AgentStatus.ACTIVE)
    await layer.agents.deprecate_agent(agent.agent_id)

    with pytest.raises(InvalidStateError):
        await layer.agents.disable_agent(agent.agent_id)


async def test_discovery_by_department_role_capability(mongo_db) -> None:
    layer = build_service_layer(mongo_db)
    for idx in range(3):
        await _register(
            layer,
            f"dev_{idx}",
            slug=f"developer-{idx}",
            department=AgentDepartment.DEVELOPMENT,
            status=AgentStatus.ACTIVE,
            capabilities=[AgentCapability.DEVELOPMENT_BACKEND],
        )

    devs = await layer.agents.find_by_department(AgentDepartment.DEVELOPMENT)
    assert len(devs) == 3

    developers = await layer.agents.find_by_role(AgentRole.DEVELOPER)
    assert len(developers) == 3

    backend = await layer.agents.find_by_capability(AgentCapability.DEVELOPMENT_BACKEND)
    assert len(backend) == 3

    inactive = await layer.agents.find_by_department(
        AgentDepartment.DEVELOPMENT, status=AgentStatus.INACTIVE
    )
    assert inactive == []


async def test_list_agents_filters_and_pagination(mongo_db) -> None:
    layer = build_service_layer(mongo_db)
    await _register(layer, "one", status=AgentStatus.ACTIVE)
    await _register(layer, "two", status=AgentStatus.REGISTERED)

    all_pages = await layer.agents.list_agents(page_size=1)
    assert all_pages.total == 2
    assert all_pages.has_next is True
    assert len(all_pages.items) == 1

    active = await layer.agents.list_agents(status=AgentStatus.ACTIVE)
    assert [a.agent_id for a in active.items] == ["one"]


async def test_find_eligible_foundation(mongo_db) -> None:
    layer = build_service_layer(mongo_db)
    backend = await _register(
        layer,
        "backend",
        status=AgentStatus.ACTIVE,
        capabilities=[AgentCapability.DEVELOPMENT_BACKEND],
    )
    await _register(
        layer,
        "frontend",
        status=AgentStatus.ACTIVE,
        capabilities=[AgentCapability.DEVELOPMENT_FRONTEND],
    )
    # Not active, so never eligible
    await _register(
        layer,
        "rare",
        status=AgentStatus.REGISTERED,
        capabilities=[AgentCapability.DEVELOPMENT_BACKEND],
    )

    eligible = await layer.agents.find_eligible(
        AgentEligibilityQuery(required_capabilities=[AgentCapability.DEVELOPMENT_BACKEND])
    )
    assert [a.agent_id for a in eligible] == ["backend"]
    assert all(a.status is AgentStatus.ACTIVE for a in eligible)

    # dict form works too
    by_dict = await layer.agents.find_eligible(
        {"required_capabilities": [AgentCapability.DEVELOPMENT_BACKEND]}
    )
    assert [a.agent_id for a in by_dict] == [backend.agent_id]


async def test_can_use_tool_registry_check(mongo_db) -> None:
    layer = build_service_layer(mongo_db)
    await _register(
        layer,
        "read_only",
        status=AgentStatus.ACTIVE,
        tools=ToolSet(allowed_tool_ids=["read_file"]),
    )
    assert await layer.agents.can_use_tool("read_only", "read_file") is True
    assert await layer.agents.can_use_tool("read_only", "read_file", level="write") is False
    assert await layer.agents.can_use_tool("read_only", "run_terminal") is False

    with pytest.raises(NotFoundError):
        await layer.agents.can_use_tool("missing", "read_file")


async def test_seed_is_idempotent(mongo_db) -> None:
    layer = build_service_layer(mongo_db)

    first = await layer.agents.run_seed()
    assert len(first) == 8
    slugs = {a.slug for a in first}
    assert slugs == {
        "orchestrator",
        "product-manager",
        "system-architect",
        "backend-developer",
        "frontend-developer",
        "code-reviewer",
        "qa-lead",
        "test-automation",
    }
    # every seeded agent is active with model/permissions/autonomy configured
    for a in first:
        assert a.status is AgentStatus.ACTIVE
        assert a.capabilities, f"{a.agent_id} must declare capabilities"
        assert a.system_prompt_ref, f"{a.agent_id} must reference a system prompt"
        assert a.autonomy is not None and a.autonomy.level >= 1

    # Re-running must not create duplicates or overwrite anything
    second = await layer.agents.run_seed()
    assert len(second) == 8
    assert await mongo_db["agents"].count_documents({}) == 8
    assert (await mongo_db["events"].count_documents({"type": "agent.created"})) == 8


async def test_least_privilege_denied_for_high_risk_registration(mongo_db) -> None:
    layer = build_service_layer(mongo_db)
    with pytest.raises(PolicyViolationError):
        await _register(
            layer,
            "sneaky",
            permissions={"secrets": {"allowed_secret_names": ["prod_api_key"]}},
        )


async def test_trusted_registration_allows_high_risk(mongo_db) -> None:
    layer = build_service_layer(mongo_db)
    agent = await _register(
        layer,
        "trusted_dev",
        trusted=True,
        permissions={"code_execution": {"allowed": True, "sandbox": "workspaces/default"}},
    )
    assert agent.permissions.code_execution.allowed is True
