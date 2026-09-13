"""Agent runtime (STEP 5): provider-independent execution of agent definitions.

A run resolves the agent definition, validates the execution context, builds
prepared instructions, calls the model abstraction (:mod:`aiagent.runtime.
gateway`), captures output/usage, and persists an :class:`AgentRun` document.
Nothing here executes tools, runs tasks, or schedules workflows - those are
later steps.

Public API (used by the composition root):

* :class:`AgentRuntimeService` - the runtime orchestration entry point
* :class:`ModelGateway` / :class:`ModelProviderRegistry` - model abstraction
"""

from aiagent.runtime.gateway import ModelGateway, ModelProviderRegistry
from aiagent.runtime.service import AgentRuntimeService

__all__ = ["AgentRuntimeService", "ModelGateway", "ModelProviderRegistry"]
