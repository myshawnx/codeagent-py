"""MCP preset configuration helpers."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field


class MCPServerConfig(BaseModel):
    """Configuration for a single stdio MCP server."""

    command: list[str]
    description: str = ""
    env: dict[str, str] = Field(default_factory=dict)
    source: str = "custom"
    confirm_tools: list[str] = Field(default_factory=list)


class MCPConfig(BaseModel):
    """The .agent/mcp.json file format."""

    servers: dict[str, MCPServerConfig] = Field(default_factory=dict)


PRESETS: dict[str, MCPServerConfig] = {
    "filesystem": MCPServerConfig(
        command=["npx", "-y", "@modelcontextprotocol/server-filesystem", "."],
        description="Expose the current workspace through the reference filesystem MCP server.",
        source="preset:filesystem",
        confirm_tools=["write_file", "create_directory", "move_file"],
    ),
    "github": MCPServerConfig(
        command=["npx", "-y", "@modelcontextprotocol/server-github"],
        description="GitHub issue and pull-request tools using a token from the environment.",
        env={"GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_TOKEN}"},
        source="preset:github",
        confirm_tools=["create_pull_request", "create_issue", "add_issue_comment"],
    ),
}


def mcp_config_path(cwd: str | Path) -> Path:
    """Return the MCP config path for a workspace."""
    return Path(cwd) / ".agent" / "mcp.json"


def list_presets() -> dict[str, MCPServerConfig]:
    """Return available built-in MCP presets."""
    return {name: config.model_copy(deep=True) for name, config in PRESETS.items()}


def load_mcp_config(cwd: str | Path) -> MCPConfig:
    """Load .agent/mcp.json, accepting the current and legacy list formats."""
    path = mcp_config_path(cwd)
    if not path.exists():
        return MCPConfig()

    data = json.loads(path.read_text(encoding="utf-8"))
    if "servers" not in data:
        # Legacy shape: {"name": ["cmd", "..."]}.
        return MCPConfig(
            servers={
                name: MCPServerConfig(command=command)
                for name, command in data.items()
                if isinstance(command, list)
            }
        )

    return MCPConfig.model_validate(data)


def save_mcp_config(cwd: str | Path, config: MCPConfig) -> Path:
    """Write .agent/mcp.json."""
    path = mcp_config_path(cwd)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(config.model_dump_json(indent=2), encoding="utf-8")
    return path


def add_preset(
    cwd: str | Path,
    preset_name: str,
    server_name: str | None = None,
) -> MCPServerConfig:
    """Add a built-in preset to .agent/mcp.json."""
    presets = list_presets()
    if preset_name not in presets:
        raise ValueError(f"Unknown MCP preset: {preset_name}")

    config = load_mcp_config(cwd)
    name = server_name or preset_name
    server = presets[preset_name]
    config.servers[name] = server
    save_mcp_config(cwd, config)
    return server


def remove_server(cwd: str | Path, server_name: str) -> bool:
    """Remove a configured MCP server."""
    config = load_mcp_config(cwd)
    if server_name not in config.servers:
        return False

    del config.servers[server_name]
    save_mcp_config(cwd, config)
    return True
