"""Model gateway: validate config, select provider, call, normalize (docs/plan/12).

The gateway owns *calling* models: it resolves the provider, validates the
request, enforces a wall-clock timeout, and normalizes every outcome into
:class:`aiagent.runtime.errors` so callers never see driver exceptions.
Model *routing/fallback* (plan 12 ``fallback_models``) and retrying are NOT
the gateway's job - the runtime orchestrates the state machine and retries.

Provider instances are discovered through the :class:`ModelProviderRegistry`,
which is populated by the composition root.
"""

from __future__ import annotations

import asyncio

from aiagent.core.config import RuntimeSettings
from aiagent.runtime.errors import (
    InvalidModelResponseError,
    ModelError,
    ProviderCancelledError,
    ProviderNotFoundError,
    ProviderTimeoutError,
    TransientProviderError,
)
from aiagent.runtime.models import (
    CancelToken,
    ModelProvider,
    ModelRequest,
    ModelResponse,
)


class ModelProviderRegistry:
    """Name -> provider instance registry (a provider may be registered once)."""

    def __init__(self) -> None:
        self._providers: dict[str, ModelProvider] = {}

    def register(self, provider: ModelProvider) -> None:
        if provider.name in self._providers:
            raise ValueError(f"provider {provider.name!r} already registered")
        if not provider.name:
            raise ValueError("provider must have a non-empty name")
        self._providers[provider.name] = provider

    def get(self, name: str) -> ModelProvider | None:
        return self._providers.get(name)

    def supports(self, name: str) -> bool:
        return name in self._providers

    def names(self) -> list[str]:
        return sorted(self._providers)


class ModelGateway:
    """Entry point for a single model call (no retries, no fallbacks)."""

    def __init__(
        self,
        registry: ModelProviderRegistry,
        *,
        settings: RuntimeSettings | None = None,
    ) -> None:
        self._registry = registry
        self._settings = settings or RuntimeSettings()

    async def complete(
        self,
        *,
        provider: str,
        request: ModelRequest,
        cancel_token: CancelToken | None = None,
        timeout_secs: float | None = None,
    ) -> ModelResponse:
        """Execute one model call with a wall-clock timeout, normalized errors.

        Raises (all from :mod:`aiagent.runtime.errors`):
        * :class:`ProviderNotFoundError` for unknown providers,
        * :class:`ProviderTimeoutError` when the wall clock expires,
        * :class:`ProviderCancelledError` when the caller cancelled,
        * a provider-specific error subclass for provider failures.
        """
        instance = self._registry.get(provider)
        if instance is None:
            raise ProviderNotFoundError(f"provider {provider!r} is not available")

        timeout = timeout_secs if timeout_secs is not None else self._settings.default_timeout_secs
        try:
            response = await asyncio.wait_for(
                instance.complete(request, cancel_token=cancel_token), timeout=timeout
            )
        except TimeoutError as exc:
            raise ProviderTimeoutError(
                f"provider {provider!r} timed out after {timeout:g}s"
            ) from exc
        except asyncio.CancelledError as exc:
            raise ProviderCancelledError(f"provider {provider!r} call cancelled") from exc
        except ProviderCancelledError:
            raise
        except ModelError:
            raise
        except Exception as exc:  # noqa: BLE001 - provider failures become typed errors
            raise TransientProviderError(
                f"provider {provider!r} failed: {type(exc).__name__}"
            ) from exc

        if response.content is None or not response.content.strip():
            raise InvalidModelResponseError(f"provider {provider!r} returned empty content")

        return response

    @staticmethod
    def to_request(
        *,
        model_id: str,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
        temperature: float | None = None,
    ) -> ModelRequest:
        return ModelRequest(
            model_id=model_id,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    def supports(self, provider: str) -> bool:
        """True when a provider is registered under ``provider``."""
        return self._registry.supports(provider)
