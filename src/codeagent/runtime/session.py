"""Agent Session - 会话管理"""

from pathlib import Path
from typing import Any

from anthropic import Anthropic

from .extensions import Extension, ExtensionAPI, ExtensionManager
from .loop import AgentLoop
from .tools import create_builtin_tools
from .types import Tool


class SessionAPI(ExtensionAPI):
    """Session 实现的 ExtensionAPI"""
    
    def __init__(self, session: "AgentSession"):
        self.session = session
    
    def register_tool(self, tool: Tool) -> None:
        self.session.register_tool(tool)
    
    def set_active_tools(self, names: list[str]) -> None:
        self.session.set_active_tools(names)
    
    def append_entry(self, entry_type: str, data: dict) -> None:
        self.session.append_entry(entry_type, data)
    
    def send_message(self, content: str) -> None:
        # 暂时不实现，P1 专注于基础功能
        pass


class AgentSession:
    """Agent 会话"""
    
    def __init__(
        self,
        cwd: str,
        api_key: str | None = None,
        model: str = "claude-sonnet-4-6",
        extensions: list[Extension] | None = None,
    ):
        self.cwd = cwd
        self.model = model
        self.client = Anthropic(api_key=api_key)
        
        # 工具
        self.tools: dict[str, Tool] = {}
        self.active_tool_names: list[str] = []
        
        # 自定义 entries（用于记录轨迹）
        self.custom_entries: list[dict] = []
        
        # 扩展
        self.extensions = extensions or []
        self.extension_api = SessionAPI(self)
        self.extension_manager = ExtensionManager(self.extensions, self.extension_api)
        
        # 初始化内置工具
        builtin_tools = create_builtin_tools(cwd)
        for tool in builtin_tools:
            self.register_tool(tool)
        self.set_active_tools([t.name for t in builtin_tools])
    
    def register_tool(self, tool: Tool) -> None:
        """注册工具"""
        self.tools[tool.name] = tool
    
    def set_active_tools(self, names: list[str]) -> None:
        """设置活跃工具"""
        self.active_tool_names = names
    
    def append_entry(self, entry_type: str, data: dict) -> None:
        """追加自定义 entry"""
        self.custom_entries.append({
            "type": entry_type,
            "data": data,
        })
    
    async def run(self, prompt: str) -> str:
        """运行 Agent"""
        # 触发 session_start
        self.extension_manager.fire_session_start()
        
        # 获取活跃工具
        active_tools = {
            name: self.tools[name]
            for name in self.active_tool_names
            if name in self.tools
        }
        
        # 创建并运行主循环
        loop = AgentLoop(
            client=self.client,
            model=self.model,
            tools=active_tools,
            extension_manager=self.extension_manager,
        )
        
        try:
            result = await loop.run(prompt)
            return result
        finally:
            # 触发 session_end
            self.extension_manager.fire_session_end()
