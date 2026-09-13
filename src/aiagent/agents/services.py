"""Agent Registry service (STEP 4).

Owns the lifecycle of agent *definitions*: register, look up, list, update,
enable/disable/deprecate (validated state machine), capability/department/role
discovery, and the registry-level task-eligibility foundation.

It does **not** execute agents - the agent runtime, model/tool calls and task
assignment are later steps (docs/plan/06, 08).  Every mutation is audited and
typed events are emitted so the observability layer can trace them.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel

from aiagent.agents.catalog import (
    AgentEligibilityQuery,
    assert_not_high_risk,
    is_eligible,
    requires_trusted,
)
from aiagent.agents.seed import seed_system_agents
from aiagent.agents.status import assert_transition
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
    ToolPermissionLevel,
)
from aiagent.db.models import Agent, AutonomyConfig, ModelConfig, ResourcePermissions, ToolSet
from aiagent.db.repositories import Page, Repositories
from aiagent.events.audit import AuditLogger, snapshot
from aiagent.events.publisher import EventPublisher
from aiagent.events.types import DomainEvent, EventType

#: Sentinel marking "field not supplied" so ``None`` still means "set to None".
_UNSET: object = object()

#: Config-block fields that auto-bump the agent version on change.
_CONFIG_FIELDS = ("model", "tools", "permissions", "autonomy")


def _as_mongo(value: Any) -> Any:
    """Normalise embedded pydantic models to plain Mongo-ready dicts."""
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    return value


def _dump(value: Any) -> Any:
    """``model_dump`` when set, else ``None`` (for config-block diffing)."""
    return value.model_dump() if value is not None else None


def _default_slug(agent_id: str) -> str:
    return agent_id.replace("_", "-").lower()


#: Config-block fields that auto-bump the agent version on change.
_CONFIG_FIELDS = ("model", "tools", "permissions", "autonomy")


def _bump(version: str) -> str:
    """Return the next compatible patch version for a given semver string."""
    major, minor, patch = (int(part) for part in version.split("."))
    return f"{major}.{minor}.{patch + 1}"


def _aspect_changed(current: Agent, updated: Agent) -> set[str]:
    """Which config aspects differ between two snapshots (observability)."""
    changed: set[str] = set()
    if _dump(current.model) != _dump(updated.model):
        changed.add("model")
    if _dump(current.tools) != _dump(updated.tools):
        changed.add("tools")
    if _dump(current.permissions) != _dump(updated.permissions):
        changed.add("permissions")
    if _dump(current.autonomy) != _dump(updated.autonomy):
        changed.add("autonomy")
    return changed


class AgentRegistryService:
    def __init__(
        self,
        repos: Repositories,
        publisher: EventPublisher,
        audit: AuditLogger,
    ) -> None:
        self._repos = repos
        self._publisher = publisher
        self._audit = audit

    # ------------------------------------------------------------------
    # Registration & lookup
    # ------------------------------------------------------------------

    async def register_agent(
        self,
        agent_id: str,
        *,
        name: str | None = None,
        slug: str | None = None,
        description: str | None = None,
        role: AgentRole | str = AgentRole.DEVELOPER,
        department: AgentDepartment | str | None = None,
        status: AgentStatus | str = AgentStatus.REGISTERED,
        version: str = "1.0.0",
        capabilities: Sequence[AgentCapability | str] | None = None,
        system_prompt_ref: str | None = None,
        model: ModelConfig | dict[str, Any] | None = None,
        tools: ToolSet | dict[str, Any] | None = None,
        permissions: ResourcePermissions | dict[str, Any] | None = None,
        autonomy: AutonomyConfig | dict[str, Any] | None = None,
        config: dict[str, Any] | None = None,
        trusted: bool = False,
    ) -> Agent:
        """Register a new agent definition (status state machine validated).

        * ``slug`` defaults to a dashed form of ``agent_id`` for ad-hoc
          agents; the seed supplies explicit slugs for system agents.
        * Four distinct aspects are stored separately (identity, runtime
          model config, tool permissions, autonomy) - no monolithic blob.
        * Least-privilege guardrail: configurations that would grant
          high-risk permissions (ADMIN tools, secrets, unrestricted
          filesystem, unrestricted egress, code execution, migration/push)
          are rejected unless ``trusted=True`` (system seed / admin path).
        """
        slug = slug or _default_slug(agent_id)

        if await self._repos.agents.find_by_agent_id(agent_id) is not None:
            raise ConflictError(f"agent {agent_id!r} already registered")
        if await self._repos.agents.find_by_slug(slug) is not None:
            raise ConflictError(f"agent slug {slug!r} already in use")

        agent = Agent(
            agent_id=agent_id,
            name=name or agent_id,
            slug=slug,
            description=description,
            role=AgentRole(role),
            department=AgentDepartment(department) if department else None,
            status=AgentStatus(status) if status is not None else AgentStatus.REGISTERED,
            version=version,
            capabilities=[AgentCapability(c) for c in capabilities or []],
            system_prompt_ref=system_prompt_ref,
            model=ModelConfig.model_validate(model) if model else None,
            tools=ToolSet.model_validate(tools) if tools else None,
            permissions=(ResourcePermissions.model_validate(permissions) if permissions else None),
            autonomy=AutonomyConfig.model_validate(autonomy) if autonomy else None,
            config=config or {},
        )

        if requires_trusted(agent) and not trusted:
            assert_not_high_risk(agent)  # raises PolicyViolationError
        if agent.status is not AgentStatus.REGISTERED and agent.status is not AgentStatus.ACTIVE:
            raise PolicyViolationError("agents may only be registered as registered or active")

        await self._repos.agents.create(agent)

        await self._publisher.publish(
            DomainEvent.build(
                EventType.AGENT_CREATED,
                payload={
                    "agent_id": agent.agent_id,
                    "slug": agent.slug,
                    "role": str(agent.role),
                    "department": str(agent.department) if agent.department else None,
                },
                emitted_by="service:agent-registry",
            )
        )
        await self._audit.record(
            action="agent.register",
            resource_type="agent",
            resource_id=agent.id,
            after=snapshot(agent),
        )
        return agent

    async def get_agent(self, doc_id: str) -> Agent | None:
        """Look up an agent definition by its document id."""
        return await self._repos.agents.find_by_id(doc_id)

    async def find_agent(self, agent_id: str) -> Agent | None:
        return await self._repos.agents.find_by_agent_id(agent_id)

    async def find_by_slug(self, slug: str) -> Agent | None:
        return await self._repos.agents.find_by_slug(slug)

    async def find_any(self, slug: str, agent_id: str) -> Agent | None:
        """Resolve an agent by slug first, then by stable agent_id (seed)."""
        return await self._repos.agents.find_by_slug(
            slug
        ) or await self._repos.agents.find_by_agent_id(agent_id)

    async def list_agents(
        self,
        *,
        status: AgentStatus | str | None = None,
        department: AgentDepartment | str | None = None,
        role: AgentRole | str | None = None,
        capability: AgentCapability | str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Page[Agent]:
        query: dict[str, Any] = {}
        if status:
            query["status"] = AgentStatus(status).value
        if department:
            query["department"] = AgentDepartment(department).value
        if role:
            query["role"] = AgentRole(role).value
        if capability:
            query["capabilities"] = AgentCapability(capability).value
        return await self._repos.agents.paginate(
            query, sort=[("created_at", 1)], page=page, page_size=page_size
        )

    # ------------------------------------------------------------------
    # Update (versioned, observability events)
    # ------------------------------------------------------------------

    async def update_agent(
        self,
        doc_id: str,
        *,
        name: str | None = None,
        slug: str | None = None,
        description: str | None = None,
        role: AgentRole | str | None = None,
        department: AgentDepartment | str | None = None,
        version: str | None = None,
        capabilities: list[AgentCapability | str] | None = None,
        system_prompt_ref: str | None = None,
        model: Any = _UNSET,
        tools: Any = _UNSET,
        permissions: Any = _UNSET,
        autonomy: Any = _UNSET,
        config: Any = _UNSET,
        trusted: bool = False,
        status: Any = _UNSET,
    ) -> Agent:
        """Partial update of an agent definition.

        ``status`` is not a supported update - registry status changes must
        go through :meth:`enable_agent` / :meth:`disable_agent` /
        :meth:`deprecate_agent` (validated transitions).  Config-block
        changes are auto-versioned (patch bump) and observable via
        ``agent.*_changed`` events + before/after audit diffs.
        """
        if status is not _UNSET:
            raise InvalidStateError("agent status must be changed via enable/disable/deprecate")

        current = await self._repos.agents.find_by_id(doc_id)
        if current is None:
            raise NotFoundError(f"agent {doc_id} not found")

        changes: dict[str, Any] = {}
        if name is not None:
            changes["name"] = name
        if description is not None:
            changes["description"] = description
        if role is not None:
            changes["role"] = AgentRole(role)
        if department is not None:
            changes["department"] = AgentDepartment(department)
        if capabilities is not None:
            changes["capabilities"] = [AgentCapability(c) for c in capabilities]
        if system_prompt_ref is not None:
            changes["system_prompt_ref"] = system_prompt_ref
        if slug is not None:
            if slug != current.slug and await self._repos.agents.find_by_slug(slug) is not None:
                raise ConflictError(f"agent slug {slug!r} already in use")
            changes["slug"] = slug

        block_updates: dict[str, Any] = {}
        for field in _CONFIG_FIELDS:
            if locals()[field] is not _UNSET:  # type: ignore[assignment]
                block_updates[field] = _as_mongo(locals()[field])  # type: ignore[assignment]
        if config is not _UNSET:
            block_updates["config"] = _as_mongo(config)

        if version is not None:
            changes["version"] = self._validated_version(version, current.version)
        elif block_updates:
            changes["version"] = _bump(current.version)

        if not changes and not block_updates:
            return current

        changes.update(block_updates)

        # Re-validate the merged document (server-side shape) and enforce the
        # least-privilege policy BEFORE anything is persisted.
        merged = current.model_dump()
        merged.update(changes)
        candidate = Agent.model_validate(merged)
        if requires_trusted(candidate) and not trusted:
            raise PolicyViolationError(
                "update would grant high-risk permissions; compensate or mark trusted"
            )

        updated = await self._repos.agents.update(doc_id, changes)
        if updated is None:
            raise NotFoundError(f"agent {doc_id} not found")

        await self._publisher.publish(
            DomainEvent.build(
                EventType.AGENT_UPDATED,
                payload={
                    "agent_id": current.agent_id,
                    "slug": updated.slug,
                    "version": updated.version,
                },
                emitted_by="service:agent-registry",
            )
        )
        for aspect in sorted(_aspect_changed(current, updated)):
            event_type = {
                "model": EventType.AGENT_MODEL_CHANGED,
                "permissions": EventType.AGENT_PERMISSIONS_CHANGED,
                "autonomy": EventType.AGENT_AUTONOMY_CHANGED,
            }.get(aspect)
            if event_type:
                await self._publisher.publish(
                    DomainEvent.build(
                        event_type,
                        payload={
                            "agent_id": current.agent_id,
                            "slug": updated.slug,
                            "version": updated.version,
                        },
                        emitted_by="service:agent-registry",
                    )
                )
        await self._audit.record(
            action="agent.update",
            resource_type="agent",
            resource_id=doc_id,
            before=snapshot(current),
            after=snapshot(updated),
        )
        return updated

    @staticmethod
    def _validated_version(new_version: str, current: str) -> str:
        """Reject downgrades; patch bumps keep history readable."""
        new_parts = [int(p) for p in new_version.split(".")]
        current_parts = [int(p) for p in current.split(".")]
        if new_parts < current_parts:
            raise InvalidStateError(
                f"version {new_version} is older than current {current}; "
                "version history is append-only"
            )
        return new_version

    # ------------------------------------------------------------------
    # Status transitions (validated state machine)
    # ------------------------------------------------------------------

    async def _transition(self, agent_id: str, next_status: AgentStatus, /) -> Agent:
        current = await self._repos.agents.find_by_agent_id(agent_id)
        if current is None:
            raise NotFoundError(f"agent {agent_id} not found")
        assert_transition(current.status, next_status)

        updated = await self._repos.agents.update(current.id, {"status": next_status.value})
        if updated is None:
            raise NotFoundError(f"agent {agent_id} not found")

        event_type = {
            AgentStatus.ACTIVE: EventType.AGENT_ENABLED,
            AgentStatus.DISABLED: EventType.AGENT_DISABLED,
            AgentStatus.DEPRECATED: EventType.AGENT_DEPRECATED,
        }[next_status]
        await self._publisher.publish(
            DomainEvent.build(
                event_type,
                payload={
                    "agent_id": updated.agent_id,
                    "slug": updated.slug,
                    "before": str(current.status.value),
                    "after": str(next_status.value),
                },
                emitted_by="service:agent-registry",
            )
        )
        await self._audit.record(
            action=f"agent.{next_status.value}",
            resource_type="agent",
            resource_id=current.id,
            before=snapshot(current),
            after=snapshot(updated),
        )
        return updated

    async def enable_agent(self, agent_id: str) -> Agent:
        """Activate an agent; valid from registered/inactive/disabled."""
        return await self._transition(agent_id, AgentStatus.ACTIVE)

    async def disable_agent(self, agent_id: str) -> Agent:
        """Block an agent; valid from active/inactive."""
        return await self._transition(agent_id, AgentStatus.DISABLED)

    async def deprecate_agent(self, agent_id: str) -> Agent:
        """Terminally deprecate an agent (superseded)."""
        return await self._transition(agent_id, AgentStatus.DEPRECATED)

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    async def find_by_department(
        self, department: AgentDepartment | str, *, status: AgentStatus | str = AgentStatus.ACTIVE
    ) -> list[Agent]:
        return await self._repos.agents.find_by_department(
            AgentDepartment(department).value, status=AgentStatus(status).value
        )

    async def find_by_role(
        self, role: AgentRole | str, *, status: AgentStatus | str = AgentStatus.ACTIVE
    ) -> list[Agent]:
        return await self._repos.agents.find_by_role(
            AgentRole(role).value, status=AgentStatus(status).value
        )

    async def find_by_capability(
        self, capability: AgentCapability | str, *, status: AgentStatus | str = AgentStatus.ACTIVE
    ) -> list[Agent]:
        return await self._repos.agents.find_by_capability(
            AgentCapability(capability).value, status=AgentStatus(status).value
        )

    async def find_eligible(self, query: AgentEligibilityQuery | dict[str, Any]) -> list[Agent]:
        """Return active agents whose definition satisfies *query*.

        Registry-level matching only - task assignment, queues and worker
        leasing are later steps.  Candidates are narrowed by the first
        required capability (indexed) when present, then filtered through
        :func:`aiagent.agents.catalog.is_eligible` for the full criteria.
        """
        query = AgentEligibilityQuery.model_validate(query)
        status_value = AgentStatus(query.status).value
        if query.required_capabilities:
            candidates = await self._repos.agents.find_by_capability(
                str(query.required_capabilities[0]), status=status_value
            )
        elif query.departments:
            candidates = await self._repos.agents.find_by_department(
                str(query.departments[0]), status=status_value
            )
        else:
            candidates = await self._repos.agents.find_many({"status": status_value})

        return [agent for agent in candidates if is_eligible(agent, query)]

    # ------------------------------------------------------------------
    # Tool permission check
    # ------------------------------------------------------------------

    async def can_use_tool(
        self,
        agent_id: str,
        tool_id: str,
        *,
        level: ToolPermissionLevel | str = ToolPermissionLevel.READ,
    ) -> bool:
        registry_agent = await self._repos.agents.find_by_agent_id(agent_id)
        if registry_agent is None:
            raise NotFoundError(f"agent {agent_id} not found")
        return registry_agent.can_use_tool(tool_id, level=ToolPermissionLevel(level))

    # ------------------------------------------------------------------
    # Seeding
    # ------------------------------------------------------------------

    async def run_seed(self) -> list[Agent]:
        """Idempotently create the MVP system agents (safe to repeat)."""
        return await seed_system_agents(self)
