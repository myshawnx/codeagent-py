"""ask 命令实现"""

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
from ...trace import attach_trace_writer, get_trace_dir

console = Console()


def run_ask(prompt: str, mode: str, print_mode: bool, stream: bool = False):
    """执行 ask 命令"""
    cwd = os.getcwd()
    
    # 加载配置
    config = load_agent_config(cwd)
    
    # 解析模式
    try:
        approval_mode = ApprovalMode(mode)
    except ValueError:
        console.print(f"[red]Error:[/red] Invalid mode '{mode}'")
        console.print("Valid modes: readonly, suggest, workspace-write, auto")
        return
    
    # 检查 API 密钥
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        console.print("[red]Error:[/red] ANTHROPIC_API_KEY not set")
        console.print("Please set your API key:")
        console.print("  export ANTHROPIC_API_KEY=your-key-here")
        return
    
    # 创建扩展
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
                goal=prompt,
                max_tool_calls=config.policy.limits.max_tool_calls,
                max_fix_iterations=config.policy.limits.max_fix_iterations,
                token_budget=config.policy.limits.token_budget,
                profile=config.profile,
            ),
        ),
    ]
    
    # 创建会话
    event_bus = EventBus()
    session = AgentSession(
        cwd=cwd,
        api_key=api_key,
        extensions=extensions,
        event_bus=event_bus,
    )

    # Attach trace writer to save session automatically.
    trace_dir = get_trace_dir(cwd)
    trace_path = trace_dir / f"{event_bus.session_id}.jsonl"
    trace_writer = attach_trace_writer(event_bus, trace_path)
    
    # 运行
    console.print(f"[bold blue]🤖 CodeAgent[/bold blue] ({mode} mode)")
    console.print(f"[dim]Prompt:[/dim] {prompt}\n")
    
    try:
        if stream:
            console.print("\n[bold green]✓ Response:[/bold green]")
            asyncio.run(_print_stream(session, prompt))
            console.print()
        else:
            result = asyncio.run(session.run(prompt))
            console.print("\n[bold green]✓ Response:[/bold green]")
            console.print(result)
    except Exception as e:
        console.print(f"\n[red]Error:[/red] {e}")
    finally:
        trace_writer.close()
        console.print(f"\n[dim]Trace saved: {trace_path.name}[/dim]")


async def _print_stream(session: AgentSession, prompt: str) -> None:
    async for event in session.run_stream(prompt):
        if event.type == EventType.MODEL_TEXT_DELTA:
            console.print(event.payload.get("text", ""), end="")
        elif event.type == EventType.TOOL_CALL_REQUESTED:
            tool = event.payload.get("tool", "tool")
            console.print(f"\n[dim]→ {tool}[/dim]")
