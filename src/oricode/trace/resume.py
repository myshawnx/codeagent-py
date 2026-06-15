"""Reconstruct conversation state from JSONL runtime traces."""

from __future__ import annotations

from ..providers import ModelMessage
from ..runtime.events import Event, EventType


class TraceReconstructionError(ValueError):
    """Raised when a trace is not safe or complete enough to resume."""


def reconstruct_messages(events: list[Event]) -> list[ModelMessage]:
    """Rebuild normalized conversation messages from runtime events.

    This implements linear resume: each ``model_request`` carries the full
    provider input messages for that turn, and each ``model_response`` appends
    the assistant content that ended the turn. Older traces without those full
    payloads fail explicitly instead of guessing.
    """
    messages: list[ModelMessage] = []
    saw_model_request = False

    for event in events:
        if event.type == EventType.ERROR:
            error = event.payload.get("error", "unknown error")
            raise TraceReconstructionError(
                f"Trace contains runtime error and cannot be safely resumed: {error}"
            )

        if event.type == EventType.MODEL_REQUEST:
            raw_messages = event.payload.get("messages")
            if raw_messages is None:
                raise TraceReconstructionError(
                    "Trace model_request event does not contain resumable messages"
                )
            messages = [ModelMessage.model_validate(m) for m in raw_messages]
            saw_model_request = True
            continue

        if event.type == EventType.MODEL_RESPONSE:
            raw_content = event.payload.get("content")
            if raw_content is None:
                raise TraceReconstructionError(
                    "Trace model_response event does not contain assistant content"
                )
            messages.append(ModelMessage(role="assistant", content=raw_content))

    if not saw_model_request:
        raise TraceReconstructionError("Trace does not contain a model_request event")
    if not messages:
        raise TraceReconstructionError("Trace did not reconstruct any messages")

    return messages
