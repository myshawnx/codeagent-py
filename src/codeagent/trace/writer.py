"""JSONL session trace persistence.

The event bus emits structured events during a session. This module writes them
to a JSONL file (one event per line) so sessions can be inspected, replayed, or
exported for eval analysis.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..runtime.events import Event, EventBus


class TraceWriter:
    """Writes events to a JSONL trace file as they occur."""

    def __init__(self, trace_path: Path):
        self.trace_path = trace_path
        self.trace_path.parent.mkdir(parents=True, exist_ok=True)
        self._file = open(trace_path, "w", encoding="utf-8")

    def write_event(self, event: Event) -> None:
        """Write a single event to the trace file."""
        line = json.dumps(event.to_dict(), ensure_ascii=False)
        self._file.write(line + "\n")
        self._file.flush()

    def close(self) -> None:
        """Close the trace file."""
        if self._file and not self._file.closed:
            self._file.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def attach_trace_writer(event_bus: EventBus, trace_path: Path) -> TraceWriter:
    """Attach a trace writer to an event bus so events are persisted live."""
    writer = TraceWriter(trace_path)
    event_bus.subscribe(writer.write_event)
    return writer


def read_trace(trace_path: Path) -> list[Event]:
    """Read all events from a JSONL trace file."""
    if not trace_path.exists():
        return []

    events = []
    with open(trace_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                events.append(Event.from_dict(data))
            except (json.JSONDecodeError, KeyError, ValueError):
                # Malformed line — skip it.
                continue
    return events


def get_trace_dir(cwd: str) -> Path:
    """Return the directory where session traces are stored."""
    return Path(cwd) / ".agent" / "sessions"


def find_session_trace(cwd: str, session_id: str) -> Path | None:
    """Find a trace by exact session id or unique prefix."""
    trace_dir = get_trace_dir(cwd)
    exact = trace_dir / f"{session_id}.jsonl"
    if exact.exists():
        return exact

    if not trace_dir.exists():
        return None

    matches = sorted(trace_dir.glob(f"{session_id}*.jsonl"))
    if len(matches) == 1:
        return matches[0]
    return None


def save_session_trace(cwd: str, session_id: str, events: list[Event]) -> Path:
    """Save a list of events to a session trace file."""
    trace_dir = get_trace_dir(cwd)
    trace_dir.mkdir(parents=True, exist_ok=True)
    trace_path = trace_dir / f"{session_id}.jsonl"

    with open(trace_path, "w", encoding="utf-8") as f:
        for event in events:
            line = json.dumps(event.to_dict(), ensure_ascii=False)
            f.write(line + "\n")

    return trace_path


def list_sessions(cwd: str) -> list[dict]:
    """List all session traces with summary metadata.

    Returns a list of dicts with keys: session_id, trace_path, timestamp, event_count.
    """
    trace_dir = get_trace_dir(cwd)
    if not trace_dir.exists():
        return []

    sessions = []
    for trace_path in sorted(trace_dir.glob("*.jsonl")):
        session_id = trace_path.stem
        events = read_trace(trace_path)
        if not events:
            continue

        sessions.append({
            "session_id": session_id,
            "trace_path": str(trace_path),
            "timestamp": events[0].timestamp if events else 0,
            "event_count": len(events),
        })

    return sorted(sessions, key=lambda s: s["timestamp"], reverse=True)
