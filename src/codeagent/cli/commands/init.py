"""init 命令实现"""

import os
from pathlib import Path

from rich.console import Console

from ...config.schema import PolicyConfig, ProjectProfile
from ...config.writer import write_policy_config, write_project_profile
from ...context.profile import detect_profile

console = Console()


def run_init(force: bool):
    """初始化项目配置"""
    cwd = os.getcwd()
    agent_dir = Path(cwd) / ".agent"
    
    # 检查是否已存在
    if agent_dir.exists() and not force:
        console.print("[yellow]Warning:[/yellow] .agent/ already exists")
        console.print("Use --force to reinitialize")
        return
    
    console.print("[bold blue]🔧 Initializing project...[/bold blue]\n")
    
    # 探测项目画像
    console.print("🔍 Detecting project profile...")
    profile = detect_profile(cwd)
    
    console.print(f"  Language: [green]{profile.language}[/green]")
    console.print(f"  Package Manager: [green]{profile.package_manager}[/green]")
    if profile.framework:
        console.print(f"  Framework: [green]{profile.framework}[/green]")
    if profile.test_framework:
        console.print(f"  Test Framework: [green]{profile.test_framework}[/green]")
    
    # 写入配置
    console.print("\n📝 Writing configuration...")
    
    # 默认策略
    policy = PolicyConfig()
    write_policy_config(cwd, policy)
    console.print("  ✓ .agent/policy.json")
    
    # 项目画像
    write_project_profile(cwd, profile)
    console.print("  ✓ .agent/project-profile.json")
    
    # 创建空 memory.md
    memory_path = agent_dir / "memory.md"
    if not memory_path.exists():
        memory_path.write_text("# Project Memory\n\n", encoding="utf-8")
        console.print("  ✓ .agent/memory.md")
    
    console.print("\n[bold green]✓ Initialization complete![/bold green]")
    console.print("\nYou can now run:")
    console.print("  [cyan]codeagent ask \"your question\"[/cyan]")
