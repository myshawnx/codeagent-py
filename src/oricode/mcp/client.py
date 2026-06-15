"""MCP stdio JSON-RPC 客户端（简化实现）"""

import asyncio
import json
import os
from typing import Any


class MCPClient:
    """MCP stdio 客户端"""
    
    def __init__(self, command: list[str], env: dict[str, str] | None = None):
        self.command = command
        self.env = env or {}
        self.process: asyncio.subprocess.Process | None = None
        self.request_id = 0
    
    async def start(self) -> None:
        """启动 MCP 服务器进程"""
        self.process = await asyncio.create_subprocess_exec(
            *self.command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=build_process_env(self.env),
        )
    
    async def call(self, method: str, params: dict[str, Any] | None = None) -> dict:
        """调用 MCP 方法"""
        if not self.process or not self.process.stdin or not self.process.stdout:
            raise RuntimeError("MCP client not started")
        
        self.request_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": method,
            "params": params or {},
        }
        
        # 发送请求
        request_json = json.dumps(request) + "\n"
        self.process.stdin.write(request_json.encode())
        await self.process.stdin.drain()
        
        # 读取响应
        response_line = await self.process.stdout.readline()
        response = json.loads(response_line.decode())
        
        if "error" in response:
            raise RuntimeError(f"MCP error: {response['error']}")
        
        return response.get("result", {})
    
    async def close(self) -> None:
        """关闭 MCP 客户端"""
        if self.process and self.process.stdin:
            self.process.stdin.close()
            await self.process.wait()


class MCPToolAdapter:
    """MCP 工具适配器 - 将 MCP 工具转换为 Agent 工具"""
    
    def __init__(self, client: MCPClient):
        self.client = client
    
    async def list_tools(self) -> list[dict]:
        """列出可用工具"""
        result = await self.client.call("tools/list")
        return result.get("tools", [])
    
    def create_tool_wrapper(self, tool_def: dict):
        """为 MCP 工具创建包装函数"""
        tool_name = tool_def["name"]
        
        async def wrapper(**kwargs):
            result = await self.client.call("tools/call", {
                "name": tool_name,
                "arguments": kwargs,
            })
            return result.get("content", [{}])[0].get("text", "")
        
        return wrapper


def build_process_env(config_env: dict[str, str]) -> dict[str, str]:
    """Merge MCP config env with the process environment.

    Values like ``${GITHUB_TOKEN}`` are resolved from the local environment and
    omitted if the variable is not set. This keeps secrets out of .agent/mcp.json.
    """
    env = os.environ.copy()
    for key, value in config_env.items():
        resolved = resolve_env_value(value)
        if resolved is not None:
            env[key] = resolved
    return env


def resolve_env_value(value: str) -> str | None:
    """Resolve a literal or ${VAR_NAME} environment placeholder."""
    if value.startswith("${") and value.endswith("}"):
        return os.getenv(value[2:-1])
    return value
