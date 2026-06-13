"""mcp 命令实现"""

import os
from pathlib import Path

from rich.console import Console
from rich.table import Table

console = Console()


def run_mcp(action: str, server_name: str | None):
    """管理 MCP 服务器"""
    cwd = os.getcwd()
    
    if action == "list":
        _list_servers(cwd)
    elif action == "add":
        if not server_name:
            console.print("[red]Error:[/red] server_name required for add")
            return
        console.print(f"[yellow]TODO:[/yellow] Add MCP server '{server_name}'")
        console.print("MCP integration will be fully implemented in next iteration")
    elif action == "remove":
        if not server_name:
            console.print("[red]Error:[/red] server_name required for remove")
            return
        console.print(f"[yellow]TODO:[/yellow] Remove MCP server '{server_name}'")
    else:
        console.print(f"[red]Error:[/red] Unknown action '{action}'")
        console.print("Valid actions: list, add, remove")


def _list_servers(cwd: str):
    """列出 MCP 服务器"""
    mcp_config_path = Path(cwd) / ".agent" / "mcp.json"
    
    if not mcp_config_path.exists():
        console.print("[yellow]No MCP servers configured[/yellow]")
        console.print("\nTo add a server:")
        console.print("  [cyan]codeagent mcp add <server-name>[/cyan]")
        return
    
    table = Table(title="MCP Servers")
    table.add_column("Name", style="cyan")
    table.add_column("Status", style="green")
    
    # TODO: 读取实际配置
    table.add_row("example", "Not configured")
    
    console.print(table)
