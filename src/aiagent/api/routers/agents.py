"""Agent registry API (docs/plan/29 §2.3; STEP 4).

Endpoints:

* ``GET /agents`` - list definitions (filter by status/department/role/capability)
* ``GET /agents/eligible`` - registry-level eligibility query (foundation for
  task assignment; no assignment happens here)
* ``GET /agents/{slug_or_agent_id}`` - public definition by slug or stable id
* ``GET /agents/capability/{capability}`` - active agents with a capability
* ``POST /agents`` - register a new definition (least-privilege enforced)
* ``PATCH /agents/{slug_or_agent_id}`` - update (definition blocks auto-version)
* ``POST /agents/{slug_or_agent_id}/enable|disable|deprecate`` - lifecycle

The public payload never exposes secret *values* or provider credentials -
only identifier names and references (the secret material itself lives in the
secrets vault and is never stored in the registry).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict, Field

from aiagent.api.deps import ServicesDep
from aiagent.api.envelope import ok
from aiagent.core.errors import NotFoundError
from aiagent.db.constants import (
    AgentCapability,
    AgentDepartment,
    AgentRole,
    AgentStatus,
)
from aiagent.db.models import Agent

router = APIRouter(tags=["agents"])


# ---------------------------------------------------------------------------
# Request schemas (validated at the API boundary)
# ---------------------------------------------------------------------------


class AgentModelsRequest(BaseModel):
    """Model configuration. Providers are referenced by name only - neither
    API keys nor full endpoints are accepted here (they are injected at
    runtime from the provider secrets vault)."""

    model_config = ConfigDict(extra="forbid")

    provider: str | None = None
    model: str | None = None
    fallback_models: list[str] = Field(default_factory=list)
    max_tokens: int | None = Field(default=None, ge=1)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    timeout_s: float | None = Field(default=None, gt=0)
    retry: dict[str, Any] | None = None


class AgentToolsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    allowed_tool_ids: list[str] = Field(default_factory=list)
    default_level: str = Field(default="read")
    tool_levels: dict[str, str] = Field(default_factory=dict)


class AgentPermissionsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    filesystem: dict[str, Any] | None = None
    network: dict[str, Any] | None = None
    database: dict[str, Any] | None = None
    code_execution: dict[str, Any] | None = None
    repository: dict[str, Any] | None = None
    secrets: dict[str, Any] | None = None


class AgentAutonomyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    level: int = Field(default=0, ge=0, le=5)
    approval_tiers: list[str] | None = None


class CreateAgentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_id: str = Field(min_length=1, max_length=256)
    name: str | None = Field(default=None, min_length=1, max_length=512)
    slug: str | None = Field(default=None, min_length=1, max_length=256)
    description: str | None = None
    role: AgentRole = AgentRole.DEVELOPER
    department: AgentDepartment | None = None
    status: AgentStatus = AgentStatus.REGISTERED
    version: str = "1.0.0"
    capabilities: list[AgentCapability] = Field(default_factory=list)
    system_prompt_ref: str | None = None
    model: AgentModelsRequest | None = None
    tools: AgentToolsRequest | None = None
    permissions: AgentPermissionsRequest | None = None
    autonomy: AgentAutonomyRequest | None = None
    config: dict[str, Any] | None = None
    trusted: bool = Field(default=False, description="system seed / admin elevation")


class UpdateAgentRequest(BaseModel):
    """All fields optional; only the ASAgentValidation provided set is applied.

    ``status`` intentionally has no field here - lifecycle changes use the
    enable/disable/deprecate endpoints.
    """

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=512)
    slug: str | None = Field(default=None, min_length=1, max_length=256)
    description: str | None = None
    role: AgentRole | None = None
    department: AgentDepartment | None = None
    version: str | None = None
    capabilities: list[AgentCapability] | None = None
    system_prompt_ref: str | None = None
    model: AgentModelsRequest | None = None
    tools: AgentToolsRequest | None = None
    permissions: AgentPermissionsRequest | None = None
    autonomy: AgentAutonomyRequest | None = None
    config: dict[str, Any] | None = None
    trusted: bool = False


# ---------------------------------------------------------------------------
# Public presentation (secrets-safe)
# ---------------------------------------------------------------------------


def _public_agent(agent: Agent) -> dict[str, Any]:
    """Shape for API consumers that never includes secret/material values."""
    payload = {
        "id": agent.id,
        "agent_id": agent.agent_id,
        "slug": agent.slug,
        "name": agent.name,
        "description": agent.description,
        "role": agent.role.value,
        "department": agent.department.value if agent.department else None,
        "status": agent.status.value,
        "version": agent.version,
        "capabilities": [c.value for c in agent.capabilities],
        "system_prompt_ref": agent.system_prompt_ref,
        "model": agent.model.model_dump(exclude_none=True) if agent.model else None,
        "tools": agent.tools.model_dump(exclude_none=True) if agent.tools else None,
        "permissions": (
            agent.permissions.model_dump(exclude_none=True) if agent.permissions else None
        ),
        "autonomy": agent.autonomy.model_dump(exclude_none=True) if agent.autonomy else None,
        "config": agent.config,
        "created_at": agent.created_at,
        "updated_at": agent.updated_at,
    }
    return payload


async def _resolve_agent(services: ServicesDep, handle: str) -> Agent:
    """Resolve a path handle: try slug, then stable agent_id."""
    agent = await services.agents.find_by_slug(handle)
    if agent is None:
        agent = await services.agents.find_agent(handle)
    if agent is None:
        raise NotFoundError(f"agent {handle!r} not found")
    return agent


# ---------------------------------------------------------------------------
# Routes (static paths registered before the parameter route)
# ---------------------------------------------------------------------------


@router.get("/agents", summary="List agent definitions")
async def list_agents(
    services: ServicesDep,
    status: AgentStatus | None = None,
    department: AgentDepartment | None = None,
    role: AgentRole | None = None,
    capability: AgentCapability | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
) -> dict:
    result = await services.agents.list_agents(
        status=status,
        department=department,
        role=role,
        capability=capability,
        page=page,
        page_size=page_size,
    )
    return ok(
        data={
            "items": [_public_agent(a) for a in result.items],
            "total": result.total,
            "page": result.page,
            "page_size": result.page_size,
            "has_next": result.has_next,
        }
    )


@router.get("/agents/eligible", summary="Find eligible agents (registry-level)")
async def find_eligible(
    services: ServicesDep,
    required_capabilities: list[AgentCapability] = Query(default=[]),  # noqa: B008
    departments: list[AgentDepartment] = Query(default=[]),  # noqa: B008
    roles: list[AgentRole] = Query(default=[]),  # noqa: B008
    required_tool_ids: list[str] = Query(default=[]),  # noqa: B008
    requires_write_filesystem: bool = False,
    requires_code_execution: bool = False,
    requires_network: bool = False,
    min_autonomy_level: int = Query(default=0, ge=0, le=5),
    status: AgentStatus = AgentStatus.ACTIVE,
) -> dict:
    agents = await services.agents.find_eligible(
        {
            "required_capabilities": required_capabilities,
            "departments": departments,
            "roles": roles,
            "required_tool_ids": required_tool_ids,
            "requires_write_filesystem": requires_write_filesystem,
            "requires_code_execution": requires_code_execution,
            "requires_network": requires_network,
            "min_autonomy_level": min_autonomy_level,
            "status": status,
        }
    )
    return ok(data=[_public_agent(a) for a in agents])


@router.get("/agents/capability/{capability}", summary="Agents with a capability")
async def by_capability(capability: AgentCapability, services: ServicesDep) -> dict:
    agents = await services.agents.find_by_capability(capability)
    return ok(data=[_public_agent(a) for a in agents])


@router.get("/agents/{handle}", summary="Get an agent definition by slug or agent_id")
async def get_agent(handle: str, services: ServicesDep) -> dict:
    agent = await _resolve_agent(services, handle)
    return ok(data=_public_agent(agent))


@router.post("/agents", summary="Register an agent definition", status_code=201)
async def create_agent(payload: CreateAgentRequest, services: ServicesDep) -> dict:
    agent = await services.agents.register_agent(
        agent_id=payload.agent_id,
        name=payload.name,
        slug=payload.slug,
        description=payload.description,
        role=payload.role,
        department=payload.department,
        status=payload.status,
        version=payload.version,
        capabilities=payload.capabilities,
        system_prompt_ref=payload.system_prompt_ref,
        model=payload.model.model_dump(exclude_none=True) if payload.model else None,
        tools=payload.tools.model_dump(exclude_none=True) if payload.tools else None,
        permissions=(
            payload.permissions.model_dump(exclude_none=True) if payload.permissions else None
        ),
        autonomy=payload.autonomy.model_dump(exclude_none=True) if payload.autonomy else None,
        config=payload.config,
        trusted=payload.trusted,
    )
    return ok(data=_public_agent(agent))


@router.patch("/agents/{handle}", summary="Update an agent definition")
async def update_agent(handle: str, payload: UpdateAgentRequest, services: ServicesDep) -> dict:
    agent = await _resolve_agent(services, handle)
    kwargs = payload.model_dump(exclude_unset=True)
    kwargs["trusted"] = payload.trusted
    updated = await services.agents.update_agent(agent.id, **kwargs)
    return ok(data=_public_agent(updated))


@router.post(
    "/agents/{handle}/enable",
    summary="Enable (activate) an agent",
    description="Valid from registered/inactive/disabled.",
)
async def enable_agent(handle: str, services: ServicesDep) -> dict:
    target = await _resolve_agent(services, handle)
    updated = await services.agents.enable_agent(target.agent_id)
    return ok(data=_public_agent(updated))


@router.post(
    "/agents/{handle}/disable",
    summary="Disable an agent",
    description="Valid from active/inactive.",
)
async def disable_agent(handle: str, services: ServicesDep) -> dict:
    target = await _resolve_agent(services, handle)
    updated = await services.agents.disable_agent(target.agent_id)
    return ok(data=_public_agent(updated))


@router.post(
    "/agents/{handle}/deprecate",
    summary="Deprecate an agent (terminal)",
    description="Marks an agent superseded; it can no longer be re-enabled.",
)
async def deprecate_agent(handle: str, services: ServicesDep) -> dict:
    target = await _resolve_agent(services, handle)
    updated = await services.agents.deprecate_agent(target.agent_id)
    return ok(data=_public_agent(updated))
