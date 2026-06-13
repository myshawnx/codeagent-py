"""MCP 扩展 - 集成 MCP 工具到 Agent Session"""

from ..runtime.extensions import Extension, ExtensionAPI
from ..runtime.types import Tool
from .client import MCPClient, MCPToolAdapter


class MCPExtension(Extension):
    """MCP 工具扩展"""
    
    def __init__(self, mcp_servers: dict[str, list[str]]):
        """
        mcp_servers: {name: command_args}
        例如: {"filesystem": ["npx", "-y", "@modelcontextprotocol/server-filesystem", "."]}
        """
        self.mcp_servers = mcp_servers
        self.clients: dict[str, MCPClient] = {}
        self.adapters: dict[str, MCPToolAdapter] = {}
    
    def on_session_start(self, api: ExtensionAPI) -> None:
        """启动所有 MCP 服务器并注册工具"""
        import asyncio
        
        # 在事件循环中启动
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            loop.run_until_complete(self._start_servers(api))
        finally:
            loop.close()
    
    async def _start_servers(self, api: ExtensionAPI) -> None:
        """启动 MCP 服务器"""
        for name, command in self.mcp_servers.items():
            try:
                client = MCPClient(command)
                await client.start()
                
                self.clients[name] = client
                adapter = MCPToolAdapter(client)
                self.adapters[name] = adapter
                
                # 列出工具并注册
                tools = await adapter.list_tools()
                for tool_def in tools:
                    wrapper = adapter.create_tool_wrapper(tool_def)
                    
                    tool = Tool(
                        name=f"mcp_{name}_{tool_def['name']}",
                        description=tool_def.get("description", ""),
                        parameters=tool_def.get("inputSchema", {}),
                        execute=wrapper,
                    )
                    
                    api.register_tool(tool)
                
                api.append_entry("mcp-server-started", {
                    "name": name,
                    "tools_count": len(tools),
                })
                
            except Exception as e:
                api.append_entry("mcp-server-failed", {
                    "name": name,
                    "error": str(e),
                })
    
    def on_session_end(self, api: ExtensionAPI) -> None:
        """关闭所有 MCP 服务器"""
        import asyncio
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            loop.run_until_complete(self._close_servers())
        finally:
            loop.close()
    
    async def _close_servers(self) -> None:
        """关闭 MCP 服务器"""
        for client in self.clients.values():
            await client.close()
