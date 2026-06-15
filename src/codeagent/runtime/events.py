"""Runtime event model.

A lightweight, structured event stream emitted by the agent loop. Events are
the single source of truth consumed by session persistence (JSONL traces),
eval trace capture, debugging, and any future UI. Keeping them as plain
dataclasses (not Pydantic) keeps emission cheap on the hot path.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class EventType(str, Enum):
    """Canonical lifecycle events for a single agent session."""

    SESSION_START = "session_start"
    TURN_START = "turn_start"
    MODEL_REQUEST = "model_request"
    MODEL_STREAM_START = "model_stream_start"
    MODEL_TEXT_DELTA = "model_text_delta"
    MODEL_STREAM_END = "model_stream_end"
    MODEL_RESPONSE = "model_response"
    TOOL_CALL_REQUESTED = "tool_call_requested"
    POLICY_VERDICT = "policy_verdict"
    TOOL_START = "tool_start"
    TOOL_END = "tool_end"
    TURN_END = "turn_end"
    SESSION_END = "session_end"
    ERROR = "error"


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


@dataclass
class Event:
    """A single runtime event.

    ``payload`` carries type-specific data and must be JSON-serializable so the
    event can be persisted to a JSONL trace without custom encoders.
    """

    type: EventType
    session_id: str
    payload: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=_new_id)
    parent_id: str | None = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "type": self.type.value,
            "session_id": self.session_id,
            "parent_id": self.parent_id,
            "payload": self.payload,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Event":
        return cls(
            type=EventType(data["type"]),
            session_id=data["session_id"],
            payload=data.get("payload", {}),
            id=data.get("id", _new_id()),
            parent_id=data.get("parent_id"),
            timestamp=data.get("timestamp", 0.0),
        )


EventListener = Callable[[Event], None]


class EventBus:
    """In-memory event collector with optional live listeners.

    The loop calls :meth:`emit`; collectors (trace writers, debuggers) either
    subscribe via :meth:`subscribe` for streaming, or read :attr:`events`
    after the fact for in-memory inspection.
    """

    def __init__(self, session_id: str | None = None):
        self.session_id = session_id or _new_id()
        self.events: list[Event] = []
        self._listeners: list[EventListener] = []

    def subscribe(self, listener: EventListener) -> None:
        self._listeners.append(listener)

    def emit(
        self,
        type: EventType,
        payload: dict[str, Any] | None = None,
        parent_id: str | None = None,
    ) -> Event:
        event = Event(
            type=type,
            session_id=self.session_id,
            payload=payload or {},
            parent_id=parent_id,
        )
        self.events.append(event)
        for listener in self._listeners:
            # A misbehaving listener must never crash the agent loop.
            try:
                listener(event)
            except Exception:  # noqa: BLE001 - defensive isolation
                pass
        return event

    def by_type(self, type: EventType) -> list[Event]:
        return [e for e in self.events if e.type == type]
