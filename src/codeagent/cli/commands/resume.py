"""resume command implementation."""

import asyncio
import os

from rich.console import Console

from ...config.loader import load_agent_config
from ...config.schema import ApprovalMode
from ...loop.guards_ext import LoopGuardsExtension
from ...loop.types import LoopGuardOptions
from ...policy.approval import (
    AutoApprovalHandler,
    DenyApprovalHandler,
    RichPromptApprovalHandler,
)
from ...policy.gateway import PolicyGateway
from ...runtime.events import EventBus, EventType
from ...runtime.session import AgentSession
from ...trace import (
    TraceReconstructionError,
    attach_trace_writer,
    find_session_trace,
    get_trace_dir,
    read_trace,
    reconstruct_messages,
)

console = Console()


def run_resume(
    session_id: str,
    prompt: str | None,
    mode: str,
    print_mode: bool,
    stream: bool = False,
) -> None:
    """Resume a previous session trace with a new prompt."""
    cwd = os.getcwd()
    trace_path = find_session_trace(cwd, session_id)
    if trace_path is None:
        console.print(f"[red]Session not found or ambiguous:[/red] {session_id}")
        return

    try:
        initial_messages = reconstruct_messages(read_trace(trace_path))
    except TraceReconstructionError as exc:
        console.print(f"[red]Cannot resume session:[/red] {exc}")
        return

    config = load_agent_config(cwd)
    try:
        approval_mode = ApprovalMode(mode)
    except ValueError:
        console.print(f"[red]Error:[/red] Invalid mode '{mode}'")
        console.print("Valid modes: readonly, suggest, workspace-write, auto")
        return

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        console.print("[red]Error:[/red] ANTHROPIC_API_KEY not set")
        console.print("Please set your API key:")
        console.print("  export ANTHROPIC_API_KEY=your-key-here")
        return

    resume_prompt = prompt or "Continue from the previous session."
    approval_handler = (
        AutoApprovalHandler()
        if approval_mode == ApprovalMode.AUTO
        else DenyApprovalHandler()
        if print_mode
        else RichPromptApprovalHandler()
    )
    extensions = [
        PolicyGateway(
            policy=config.policy,
            mode=approval_mode,
            repo_root=cwd,
            approval_handler=approval_handler,
        ),
        LoopGuardsExtension(
            options=LoopGuardOptions(
                goal=resume_prompt,
                max_tool_calls=config.policy.limits.max_tool_calls,
                max_fix_iterations=config.policy.limits.max_fix_iterations,
                token_budget=config.policy.limits.token_budget,
                profile=config.profile,
            ),
        ),
    ]

    event_bus = EventBus()
    session = AgentSession(
        cwd=cwd,
        api_key=api_key,
        extensions=extensions,
        event_bus=event_bus,
        initial_messages=initial_messages,
    )

    new_trace_path = get_trace_dir(cwd) / f"{event_bus.session_id}.jsonl"
    trace_writer = attach_trace_writer(event_bus, new_trace_path)

    console.print(f"[bold blue]↩ CodeAgent[/bold blue] resume ({mode} mode)")
    console.print(f"[dim]From:[/dim] {trace_path.name}")
    console.print(f"[dim]Prompt:[/dim] {resume_prompt}\n")

    try:
        if stream:
            console.print("[bold green]✓ Response:[/bold green]")
            asyncio.run(_print_stream(session, resume_prompt))
            console.print()
        else:
            result = asyncio.run(session.run(resume_prompt))
            console.print("\n[bold green]✓ Response:[/bold green]")
            console.print(result)
    except Exception as exc:  # noqa: BLE001
        console.print(f"\n[red]Error:[/red] {exc}")
    finally:
        trace_writer.close()
        console.print(f"\n[dim]Trace saved: {new_trace_path.name}[/dim]")


async def _print_stream(session: AgentSession, prompt: str) -> None:
    async for event in session.run_stream(prompt):
        if event.type == EventType.MODEL_TEXT_DELTA:
            console.print(event.payload.get("text", ""), end="")
        elif event.type == EventType.TOOL_CALL_REQUESTED:
            tool = event.payload.get("tool", "tool")
            console.print(f"\n[dim]→ {tool}[/dim]")
