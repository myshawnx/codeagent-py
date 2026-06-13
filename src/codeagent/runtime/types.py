"""运行时类型定义"""

from typing import Any, Callable, Coroutine, Literal, Protocol

from pydantic import BaseModel


class ToolDefinition(BaseModel):
    """工具定义"""
    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema
    

class Tool(BaseModel):
    """工具实例"""
    name: str
    description: str
    parameters: dict[str, Any]
    execute: Any  # Callable[[dict], Coroutine[Any, Any, str]]
    
    class Config:
        arbitrary_types_allowed = True


class Message(BaseModel):
    """消息"""
    role: Literal["user", "assistant"]
    content: Any  # str | list


class ToolUseBlock(BaseModel):
    """工具使用块"""
    type: Literal["tool_use"] = "tool_use"
    id: str
    name: str
    input: dict[str, Any]


class TextBlock(BaseModel):
    """文本块"""
    type: Literal["text"] = "text"
    text: str


class ToolResultBlock(BaseModel):
    """工具结果块"""
    type: Literal["tool_result"] = "tool_result"
    tool_use_id: str
    content: str
    is_error: bool = False


class Usage(BaseModel):
    """Token 使用统计"""
    input_tokens: int
    output_tokens: int
    
    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class ExtensionAPI(Protocol):
    """提供给扩展的 API"""
    
    def register_tool(self, tool: Tool) -> None:
        """注册工具"""
        ...
    
    def set_active_tools(self, names: list[str]) -> None:
        """设置活跃工具列表"""
        ...
    
    def append_entry(self, entry_type: str, data: dict) -> None:
        """追加自定义 entry"""
        ...
    
    def send_message(self, content: str) -> None:
        """发送消息给 agent"""
        ...
