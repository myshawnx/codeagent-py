"""MCP preset configuration tests."""

import json

from oricode.mcp.client import build_process_env, resolve_env_value
from oricode.mcp.extension import normalize_server_configs
from oricode.mcp.presets import (
    MCPServerConfig,
    add_preset,
    list_presets,
    load_mcp_config,
    mcp_config_path,
    remove_server,
)


class TestMCPPresets:
    """MCP preset config tests."""

    def test_list_presets_includes_filesystem_and_github(self):
        presets = list_presets()

        assert "filesystem" in presets
        assert "github" in presets
        assert presets["github"].env["GITHUB_PERSONAL_ACCESS_TOKEN"] == "${GITHUB_TOKEN}"

    def test_add_and_remove_preset(self, tmp_path):
        server = add_preset(tmp_path, "filesystem")
        config = load_mcp_config(tmp_path)

        assert server.source == "preset:filesystem"
        assert "filesystem" in config.servers
        assert config.servers["filesystem"].command[0] == "npx"
        assert mcp_config_path(tmp_path).exists()

        assert remove_server(tmp_path, "filesystem") is True
        assert load_mcp_config(tmp_path).servers == {}
        assert remove_server(tmp_path, "filesystem") is False

    def test_load_legacy_list_config(self, tmp_path):
        path = mcp_config_path(tmp_path)
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"legacy": ["python", "-m", "server"]}), encoding="utf-8")

        config = load_mcp_config(tmp_path)

        assert config.servers["legacy"].command == ["python", "-m", "server"]


class TestMCPRuntimeConfig:
    """MCP runtime config normalization tests."""

    def test_env_placeholder_resolution(self, monkeypatch):
        monkeypatch.setenv("GITHUB_TOKEN", "secret-token")
        monkeypatch.delenv("MISSING_TOKEN", raising=False)

        assert resolve_env_value("${GITHUB_TOKEN}") == "secret-token"
        assert resolve_env_value("${MISSING_TOKEN}") is None
        assert resolve_env_value("literal") == "literal"

        env = build_process_env({
            "TOKEN": "${GITHUB_TOKEN}",
            "MISSING": "${MISSING_TOKEN}",
        })
        assert env["TOKEN"] == "secret-token"
        assert "MISSING" not in env

    def test_normalize_server_configs_accepts_legacy_and_structured(self):
        configs = normalize_server_configs({
            "legacy": ["python", "-m", "server"],
            "structured": MCPServerConfig(command=["node", "server.js"]),
            "dict": {"command": ["npx", "server"], "source": "test"},
        })

        assert configs["legacy"].command == ["python", "-m", "server"]
        assert configs["structured"].command == ["node", "server.js"]
        assert configs["dict"].source == "test"
