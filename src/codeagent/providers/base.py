"""Provider adapter protocol.

A ``ModelProvider`` translates a normalized :class:`ModelRequest` into a
:class:`ModelResponse`, hiding all vendor-SDK details behind a single async
method. This is the only seam the runtime depends on, which makes the agent
loop testable offline (via :class:`MockProvider`) and portable across vendors.
"""

from __future__ import annotations

import json
from typing import Protocol, runtime_checkable

from .types import ModelRequest, ModelResponse, TokenCount


class ProviderError(RuntimeError):
    """Raised when a provider call fails (network, auth, timeout, etc.)."""


class ProviderTimeoutError(ProviderError):
    """Raised when a provider call exceeds its timeout."""


class TokenCountingNotSupported(ProviderError):
    """Raised by providers that cannot count tokens accurately."""


def estimate_model_request_tokens(
    request: ModelRequest,
    *,
    provider: str = "unknown",
) -> TokenCount:
    """Return an explicitly marked fallback estimate for ``request``.

    This fallback is intentionally centralized at the provider boundary so
    context/runtime code can see that the value is estimated instead of
    treating a rough heuristic as provider-accurate token accounting.
    """

    parts: list[str] = []
    if request.system:
        parts.append(request.system)
    for message in request.messages:
        parts.append(json.dumps(message.model_dump(), sort_keys=True))
    if request.tools:
        parts.append(
            json.dumps([tool.model_dump() for tool in request.tools], sort_keys=True)
        )

    text = "\n".join(parts)
    estimated_tokens = (len(text) + 3) // 4 if text else 0
    return TokenCount(
        input_tokens=estimated_tokens,
        estimated=True,
        provider=provider,
    )


async def count_tokens_with_fallback(
    provider: object,
    request: ModelRequest,
) -> TokenCount:
    """Count request tokens with provider accuracy when available.

    Providers that do not expose token counting, or explicitly signal that it
    is unsupported, fall back to :func:`estimate_model_request_tokens`.
    """

    provider_name = getattr(provider, "name", "unknown")
    counter = getattr(provider, "count_tokens", None)
    if counter is None:
        return estimate_model_request_tokens(request, provider=provider_name)

    try:
        return await counter(request)
    except (NotImplementedError, TokenCountingNotSupported):
        return estimate_model_request_tokens(request, provider=provider_name)


@runtime_checkable
class ModelProvider(Protocol):
    """Async provider interface.

    Implementations must be safe to call from an asyncio event loop without
    blocking it. Blocking SDKs should be wrapped (e.g. ``asyncio.to_thread``)
    or replaced with their async client.
    """

    name: str

    async def generate(self, request: ModelRequest) -> ModelResponse:
        """Produce a single model response for ``request``."""
        ...

    async def count_tokens(self, request: ModelRequest) -> TokenCount:
        """Count input tokens for ``request`` using provider-native semantics."""
        ...
