"""MCP (Model Context Protocol) 集成"""

from .presets import (
    MCPConfig,
    MCPServerConfig,
    add_preset,
    list_presets,
    load_mcp_config,
    remove_server,
    save_mcp_config,
)

__all__ = [
    "MCPConfig",
    "MCPServerConfig",
    "add_preset",
    "list_presets",
    "load_mcp_config",
    "remove_server",
    "save_mcp_config",
]
