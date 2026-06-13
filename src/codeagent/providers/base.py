"""Provider adapter protocol.

A ``ModelProvider`` translates a normalized :class:`ModelRequest` into a
:class:`ModelResponse`, hiding all vendor-SDK details behind a single async
method. This is the only seam the runtime depends on, which makes the agent
loop testable offline (via :class:`MockProvider`) and portable across vendors.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .types import ModelRequest, ModelResponse


class ProviderError(RuntimeError):
    """Raised when a provider call fails (network, auth, timeout, etc.)."""


class ProviderTimeoutError(ProviderError):
    """Raised when a provider call exceeds its timeout."""


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
