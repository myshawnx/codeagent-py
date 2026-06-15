"""Runtime type definitions.

The canonical model/content types now live in ``oricode.providers.types``.
This module keeps the tool + extension-API types and re-exports the provider
block types for backward compatibility with older imports.
"""

from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict

from .events import EventType

# Re-export normalized provider types so existing imports keep working.
from ..providers.types import (  # noqa: F401
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
    Usage,
)


class ToolDefinition(BaseModel):
    """Static description of a tool (name + JSON schema)."""

    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema


class Tool(BaseModel):
    """A runnable tool: schema plus an async ``execute`` callable."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    description: str
    parameters: dict[str, Any]
    execute: Any  # Callable[..., Awaitable[str]]
    parallel_safe: bool = False
    mutates_workspace: bool = False


class ExtensionAPI(Protocol):
    """API surface provided to extensions by the session."""

    def register_tool(self, tool: Tool) -> None: ...

    def set_active_tools(self, names: list[str]) -> None: ...

    def append_entry(self, entry_type: str, data: dict) -> None: ...

    def emit_event(self, event_type: EventType, data: dict) -> None: ...

    def send_message(self, content: str) -> None: ...
