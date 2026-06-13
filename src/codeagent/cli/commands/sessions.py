"""sessions command - list and inspect session traces."""

import os

from rich.console import Console
from rich.table import Table

from ...trace import list_sessions, read_trace

console = Console()


def run_sessions(session_id: str | None):
    """List or show session traces."""
    cwd = os.getcwd()

    if session_id:
        # Show a specific session.
        from pathlib import Path
        from ...trace import get_trace_dir

        trace_path = get_trace_dir(cwd) / f"{session_id}.jsonl"
        if not trace_path.exists():
            console.print(f"[red]Session not found:[/red] {session_id}")
            return

        events = read_trace(trace_path)
        console.print(f"[bold]Session:[/bold] {session_id}")
        console.print(f"[bold]Trace:[/bold] {trace_path}")
        console.print(f"[bold]Events:[/bold] {len(events)}\n")

        for event in events:
            console.print(f"[dim]{event.timestamp:.2f}[/dim] {event.type.value} {event.payload}")

    else:
        # List all sessions.
        sessions = list_sessions(cwd)
        if not sessions:
            console.print("[yellow]No sessions found.[/yellow]")
            console.print("Run [cyan]codeagent ask \"...\"[/cyan] to create a session.")
            return

        table = Table(title="Agent Sessions")
        table.add_column("Session ID", style="cyan")
        table.add_column("Events", justify="right")
        table.add_column("Timestamp", style="dim")

        for session in sessions:
            from datetime import datetime
            ts = datetime.fromtimestamp(session["timestamp"]).strftime("%Y-%m-%d %H:%M:%S")
            table.add_row(
                session["session_id"][:12],
                str(session["event_count"]),
                ts,
            )

        console.print(table)
        console.print("\nShow details: [cyan]codeagent sessions <session-id>[/cyan]")
