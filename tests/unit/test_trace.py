"""Tests for P2 JSONL session tracing."""

import json
from pathlib import Path

import pytest

from codeagent.providers import MockProvider, text_response
from codeagent.runtime.events import Event, EventBus, EventType
from codeagent.runtime.session import AgentSession
from codeagent.trace import (
    TraceWriter,
    attach_trace_writer,
    get_trace_dir,
    list_sessions,
    read_trace,
    save_session_trace,
)


class TestTraceWriterRoundTrip:
    """JSONL write/read round-trip tests."""

    def test_write_and_read_events(self, temp_repo):
        trace_path = Path(temp_repo) / "test.jsonl"
        bus = EventBus(session_id="test-session")

        # Attach writer.
        writer = attach_trace_writer(bus, trace_path)

        # Emit events.
        bus.emit(EventType.SESSION_START, {"foo": "bar"})
        bus.emit(EventType.TURN_START, {"turn": 0})
        bus.emit(EventType.SESSION_END, {})

        writer.close()

        # Read back.
        events = read_trace(trace_path)
        assert len(events) == 3
        assert events[0].type == EventType.SESSION_START
        assert events[0].payload == {"foo": "bar"}
        assert events[1].type == EventType.TURN_START
        assert events[2].type == EventType.SESSION_END

    def test_malformed_lines_are_skipped(self, temp_repo):
        trace_path = Path(temp_repo) / "bad.jsonl"
        trace_path.write_text('{"type": "session_start", "session_id": "s1", "payload": {}}\n'
                               'not json\n'
                               '{"type": "session_end", "session_id": "s1", "payload": {}}\n')

        events = read_trace(trace_path)
        assert len(events) == 2  # malformed line skipped
        assert events[0].type == EventType.SESSION_START
        assert events[1].type == EventType.SESSION_END

    def test_read_nonexistent_trace(self, temp_repo):
        events = read_trace(Path(temp_repo) / "nonexistent.jsonl")
        assert events == []


class TestSessionTracePersistence:
    """save_session_trace and list_sessions."""

    def test_save_and_list_sessions(self, temp_repo):
        bus1 = EventBus(session_id="session-1")
        bus1.emit(EventType.SESSION_START, {})
        bus1.emit(EventType.SESSION_END, {})

        bus2 = EventBus(session_id="session-2")
        bus2.emit(EventType.SESSION_START, {})

        # Save both.
        save_session_trace(temp_repo, "session-1", bus1.events)
        save_session_trace(temp_repo, "session-2", bus2.events)

        # List.
        sessions = list_sessions(temp_repo)
        assert len(sessions) == 2
        assert sessions[0]["session_id"] in ["session-1", "session-2"]
        assert sessions[0]["event_count"] in [1, 2]

    def test_list_sessions_empty(self, temp_repo):
        sessions = list_sessions(temp_repo)
        assert sessions == []


class TestTraceIntegrationWithSession:
    """Full agent session with trace capture."""

    @pytest.mark.asyncio
    async def test_session_events_captured_in_trace(self, temp_repo):
        provider = MockProvider(responses=[text_response("done")])
        bus = EventBus()
        trace_dir = get_trace_dir(temp_repo)
        trace_path = trace_dir / f"{bus.session_id}.jsonl"
        writer = attach_trace_writer(bus, trace_path)

        session = AgentSession(cwd=temp_repo, provider=provider, event_bus=bus)
        await session.run("test")

        writer.close()

        # Read trace back.
        events = read_trace(trace_path)
        assert len(events) > 0

        # Should have session lifecycle events.
        types = [e.type for e in events]
        assert EventType.SESSION_START in types
        assert EventType.TURN_START in types
        assert EventType.MODEL_REQUEST in types
        assert EventType.MODEL_RESPONSE in types
        assert EventType.SESSION_END in types
