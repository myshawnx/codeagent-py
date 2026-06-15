"""Provider-agnostic model types.

These normalized types decouple the runtime from any specific SDK's response
objects. A provider adapter is responsible for translating between these types
and the vendor SDK; the rest of the codebase only ever sees these.
"""

from __future__ import annotations

from typing import Any, Literal, Union

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Content blocks (normalized)
# ---------------------------------------------------------------------------


class TextBlock(BaseModel):
    """A block of assistant text."""

    type: Literal["text"] = "text"
    text: str


class ToolUseBlock(BaseModel):
    """A request from the model to invoke a tool."""

    type: Literal["tool_use"] = "tool_use"
    id: str
    name: str
    input: dict[str, Any] = Field(default_factory=dict)


class ToolResultBlock(BaseModel):
    """The result of a tool execution, fed back to the model."""

    type: Literal["tool_result"] = "tool_result"
    tool_use_id: str
    content: str
    is_error: bool = False


ContentBlock = Union[TextBlock, ToolUseBlock]


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------


class ModelMessage(BaseModel):
    """A single conversation message in normalized form.

    ``content`` is always a list of blocks. User messages typically carry
    ``TextBlock`` / ``ToolResultBlock``; assistant messages carry
    ``TextBlock`` / ``ToolUseBlock``.
    """

    role: Literal["user", "assistant"]
    content: list[dict[str, Any]]


# ---------------------------------------------------------------------------
# Tool schema
# ---------------------------------------------------------------------------


class ToolSchema(BaseModel):
    """JSON-schema description of a tool, provider-agnostic."""

    name: str
    description: str
    input_schema: dict[str, Any]


# ---------------------------------------------------------------------------
# Request / response
# ---------------------------------------------------------------------------


class ModelRequest(BaseModel):
    """A normalized request to a model provider."""

    model: str
    messages: list[ModelMessage]
    tools: list[ToolSchema] = Field(default_factory=list)
    system: str | None = None
    max_tokens: int = 4096
    temperature: float | None = None


class Usage(BaseModel):
    """Token usage for a single model response."""

    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def __add__(self, other: "Usage") -> "Usage":
        return Usage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
        )


class TokenCount(BaseModel):
    """Provider-level token count for a model request."""

    input_tokens: int
    estimated: bool = False
    provider: str = "unknown"


# Normalized stop reasons across providers.
StopReason = Literal["end_turn", "tool_use", "max_tokens", "stop_sequence", "error"]


class ModelResponse(BaseModel):
    """A normalized response from a model provider."""

    content: list[ContentBlock]
    stop_reason: StopReason
    usage: Usage = Field(default_factory=Usage)
    model: str = ""

    def text(self) -> str:
        """Concatenate all text blocks."""
        return "\n".join(b.text for b in self.content if isinstance(b, TextBlock))

    def tool_uses(self) -> list[ToolUseBlock]:
        """Return all tool-use blocks."""
        return [b for b in self.content if isinstance(b, ToolUseBlock)]
