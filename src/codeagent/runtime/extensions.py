"""扩展系统"""

from abc import ABC, abstractmethod
from typing import Any

from .types import ExtensionAPI, Tool


class Extension(ABC):
    """扩展基类"""
    
    def on_session_start(self, api: ExtensionAPI) -> None:
        """会话开始时调用"""
        pass
    
    def on_session_end(self, api: ExtensionAPI) -> None:
        """会话结束时调用"""
        pass
    
    def on_tool_call(self, api: ExtensionAPI, tool_name: str, tool_input: dict) -> dict[str, Any] | None:
        """
        工具调用前调用
        
        返回 {"block": True, "reason": "..."} 可以阻止工具执行
        返回 None 允许继续
        """
        return None
    
    def on_tool_result(self, api: ExtensionAPI, tool_name: str, result: Any, is_error: bool) -> None:
        """工具执行后调用"""
        pass
    
    def on_message_end(self, api: ExtensionAPI, usage: dict) -> None:
        """消息完成后调用"""
        pass


class ExtensionManager:
    """扩展管理器"""
    
    def __init__(self, extensions: list[Extension], api: ExtensionAPI):
        self.extensions = extensions
        self.api = api
    
    def fire_session_start(self) -> None:
        """触发 session_start"""
        for ext in self.extensions:
            ext.on_session_start(self.api)
    
    def fire_session_end(self) -> None:
        """触发 session_end"""
        for ext in self.extensions:
            ext.on_session_end(self.api)
    
    def fire_tool_call(self, tool_name: str, tool_input: dict) -> dict[str, Any] | None:
        """触发 tool_call，返回第一个阻止响应"""
        for ext in self.extensions:
            result = ext.on_tool_call(self.api, tool_name, tool_input)
            if result and result.get("block"):
                return result
        return None
    
    def fire_tool_result(self, tool_name: str, result: Any, is_error: bool) -> None:
        """触发 tool_result"""
        for ext in self.extensions:
            ext.on_tool_result(self.api, tool_name, result, is_error)
    
    def fire_message_end(self, usage: dict) -> None:
        """触发 message_end"""
        for ext in self.extensions:
            ext.on_message_end(self.api, usage)
