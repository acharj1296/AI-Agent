"""Model gateway: provider resolution, timeout, normalization (STEP 5)."""

from __future__ import annotations

import pytest

from aiagent.core.config import RuntimeSettings
from aiagent.runtime.errors import (
    InvalidModelResponseError,
    ProviderCancelledError,
    ProviderNotFoundError,
    ProviderTimeoutError,
)
from aiagent.runtime.gateway import ModelGateway, ModelProviderRegistry
from aiagent.runtime.models import CancelToken, ModelRequest
from aiagent.runtime.providers.mock import DeterministicMockModelProvider, ScriptedBehavior

_REQUEST = ModelRequest(
    model_id="mock-default",
    system_prompt="system",
    user_prompt="user input",
    max_tokens=64,
)


@pytest.fixture
def gateway() -> ModelGateway:
    registry = ModelProviderRegistry()
    registry.register(DeterministicMockModelProvider())
    return ModelGateway(registry, settings=RuntimeSettings())


def test_registry_register_and_lookup(gateway) -> None:
    assert gateway.supports("mock")
    assert not gateway.supports("openai")
    assert "mock" in gateway._registry.names()
    with pytest.raises(ValueError):
        gateway._registry.register(DeterministicMockModelProvider())


def test_registry_rejects_empty_name() -> None:
    registry = ModelProviderRegistry()

    class _EmptyProvider:
        name = ""

        @property
        def default_model(self) -> str | None:
            return None

        async def complete(self, request, *, cancel_token=None):
            raise NotImplementedError

    with pytest.raises(ValueError):
        registry.register(_EmptyProvider())


async def test_unknown_provider(gateway) -> None:
    with pytest.raises(ProviderNotFoundError):
        await gateway.complete(provider="openai", request=_REQUEST)


async def test_success_passthrough(gateway) -> None:
    response = await gateway.complete(provider="mock", request=_REQUEST)
    assert response.provider == "mock"
    assert response.content


async def test_provider_timeout_maps_to_typed_error(gateway) -> None:
    gateway._registry.get("mock").script([ScriptedBehavior.TIMEOUT])  # type: ignore[union-attr]
    with pytest.raises(ProviderTimeoutError):
        await gateway.complete(provider="mock", request=_REQUEST)


async def test_empty_response_maps_to_invalid_response(gateway) -> None:
    gateway._registry.get("mock").script([ScriptedBehavior.INVALID])  # type: ignore[union-attr]
    with pytest.raises(InvalidModelResponseError):
        await gateway.complete(provider="mock", request=_REQUEST)


async def test_cancelled_provider_call_propagates(gateway) -> None:
    gateway._registry.get("mock").script([ScriptedBehavior.CANCELLED])  # type: ignore[union-attr]
    with pytest.raises(ProviderCancelledError):
        await gateway.complete(provider="mock", request=_REQUEST)


async def test_wall_clock_timeout_via_short_timeout_override(gateway) -> None:
    tick = DeterministicMockModelProvider(tick_secs=0.05)
    registry = ModelProviderRegistry()
    registry.register(tick)
    gw = ModelGateway(registry, settings=RuntimeSettings(default_timeout_secs=0.001))
    with pytest.raises(ProviderTimeoutError):
        await gw.complete(provider="mock", request=_REQUEST)


async def test_cancel_token_propagates_through_gateway(gateway) -> None:
    token = CancelToken()
    token.cancel()
    with pytest.raises(ProviderCancelledError):
        await gateway.complete(provider="mock", request=_REQUEST, cancel_token=token)
