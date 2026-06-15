"""mcp 命令实现"""

import os

from rich.console import Console
from rich.table import Table

from ...mcp.presets import (
    add_preset,
    list_presets,
    load_mcp_config,
    mcp_config_path,
    remove_server,
)

console = Console()


def run_mcp(action: str, server_name: str | None):
    """管理 MCP 服务器"""
    cwd = os.getcwd()
    
    if action == "list":
        _list_servers(cwd)
    elif action == "presets":
        _list_presets()
    elif action == "add":
        if not server_name:
            console.print("[red]Error:[/red] server_name required for add")
            return
        try:
            server = add_preset(cwd, server_name)
        except ValueError:
            console.print(f"[red]Error:[/red] Unknown MCP preset '{server_name}'")
            console.print("Available presets:")
            for name in sorted(list_presets()):
                console.print(f"  - {name}")
            return
        console.print(f"[green]Added MCP preset:[/green] {server_name}")
        if server.env:
            console.print(
                "[yellow]Note:[/yellow] this preset reads credentials "
                "from environment variables"
            )
        console.print(f"[dim]Config:[/dim] {mcp_config_path(cwd)}")
    elif action == "remove":
        if not server_name:
            console.print("[red]Error:[/red] server_name required for remove")
            return
        if remove_server(cwd, server_name):
            console.print(f"[green]Removed MCP server:[/green] {server_name}")
        else:
            console.print(f"[yellow]MCP server not configured:[/yellow] {server_name}")
    else:
        console.print(f"[red]Error:[/red] Unknown action '{action}'")
        console.print("Valid actions: list, presets, add, remove")


def _list_servers(cwd: str):
    """列出 MCP 服务器"""
    config_path = mcp_config_path(cwd)
    
    if not config_path.exists():
        console.print("[yellow]No MCP servers configured[/yellow]")
        console.print("\nAvailable presets:")
        for name, preset in sorted(list_presets().items()):
            console.print(f"  [cyan]{name}[/cyan] - {preset.description}")
        console.print("\nTo add a server:")
        console.print("  [cyan]codeagent mcp add <preset-name>[/cyan]")
        return
    
    config = load_mcp_config(cwd)
    table = Table(title="MCP Servers")
    table.add_column("Name", style="cyan")
    table.add_column("Command")
    table.add_column("Source")
    table.add_column("Env")

    for name, server in sorted(config.servers.items()):
        env_keys = ", ".join(sorted(server.env)) if server.env else "-"
        table.add_row(name, " ".join(server.command), server.source, env_keys)
    
    console.print(table)


def _list_presets():
    """列出内置 MCP 预设"""
    table = Table(title="MCP Presets")
    table.add_column("Name", style="cyan")
    table.add_column("Command")
    table.add_column("Description")

    for name, preset in sorted(list_presets().items()):
        table.add_row(name, " ".join(preset.command), preset.description)

    console.print(table)
