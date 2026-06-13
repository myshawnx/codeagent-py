"""ask 命令实现"""

import asyncio
import os

from rich.console import Console

from ...config.loader import load_agent_config
from ...config.schema import ApprovalMode
from ...loop.guards_ext import LoopGuardsExtension
from ...loop.types import LoopGuardOptions
from ...policy.gateway import PolicyGateway
from ...runtime.session import AgentSession

console = Console()


def run_ask(prompt: str, mode: str, print_mode: bool):
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
    extensions = [
        PolicyGateway(
            policy=config.policy,
            mode=approval_mode,
            repo_root=cwd,
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
    session = AgentSession(
        cwd=cwd,
        api_key=api_key,
        extensions=extensions,
    )
    
    # 运行
    console.print(f"[bold blue]🤖 CodeAgent[/bold blue] ({mode} mode)")
    console.print(f"[dim]Prompt:[/dim] {prompt}\n")
    
    try:
        result = asyncio.run(session.run(prompt))
        console.print("\n[bold green]✓ Response:[/bold green]")
        console.print(result)
    except Exception as e:
        console.print(f"\n[red]Error:[/red] {e}")
