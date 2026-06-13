"""Agent 主循环 - 核心执行引擎"""

import asyncio
import uuid
from typing import Any

from anthropic import Anthropic
from anthropic.types import Message as AnthropicMessage

from .extensions import ExtensionManager
from .types import Message, TextBlock, ToolResultBlock, ToolUseBlock, Usage


class AgentLoop:
    """Agent 主循环"""
    
    def __init__(
        self,
        client: Anthropic,
        model: str,
        tools: dict[str, Any],  # {name: Tool}
        extension_manager: ExtensionManager,
        max_turns: int = 50,
    ):
        self.client = client
        self.model = model
        self.tools = tools
        self.extension_manager = extension_manager
        self.max_turns = max_turns
        self.messages: list[dict] = []
        self.total_usage = Usage(input_tokens=0, output_tokens=0)
    
    async def run(self, prompt: str) -> str:
        """
        运行 Agent 循环
        
        返回最终的助手响应文本
        """
        # 添加用户消息
        self.messages.append({"role": "user", "content": prompt})
        
        for turn in range(self.max_turns):
            # 调用 Anthropic API
            response = await self._call_api()
            
            # 更新 token 使用统计
            if response.usage:
                self.total_usage.input_tokens += response.usage.input_tokens
                self.total_usage.output_tokens += response.usage.output_tokens
                self.extension_manager.fire_message_end({
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                    "total_tokens": self.total_usage.total_tokens,
                })
            
            # 处理响应
            if response.stop_reason == "end_turn":
                # 完成
                text = self._extract_text(response.content)
                self.messages.append({"role": "assistant", "content": response.content})
                return text
            
            if response.stop_reason == "tool_use":
                # 执行工具
                assistant_content = response.content
                self.messages.append({"role": "assistant", "content": assistant_content})
                
                # 执行所有工具调用
                tool_results = await self._execute_tools(assistant_content)
                
                # 回灌工具结果
                self.messages.append({"role": "user", "content": tool_results})
                
                # 继续循环
                continue
            
            # 其他 stop_reason
            text = self._extract_text(response.content)
            self.messages.append({"role": "assistant", "content": response.content})
            return text
        
        # 达到最大轮数
        return "Maximum turns reached"
    
    async def _call_api(self) -> AnthropicMessage:
        """调用 Anthropic API"""
        # 转换工具定义为 Anthropic 格式
        tools_schema = [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.parameters,
            }
            for tool in self.tools.values()
        ]
        
        # 调用 API
        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            messages=self.messages,
            tools=tools_schema,
        )
        
        return response
    
    async def _execute_tools(self, content: list) -> list[dict]:
        """执行工具调用"""
        tool_results = []
        
        for block in content:
            if not isinstance(block, dict):
                continue
                
            if block.get("type") != "tool_use":
                continue
            
            tool_use_id = block["id"]
            tool_name = block["name"]
            tool_input = block.get("input", {})
            
            # 触发 tool_call 钩子
            verdict = self.extension_manager.fire_tool_call(tool_name, tool_input)
            if verdict and verdict.get("block"):
                # 策略拒绝
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use_id,
                    "content": f"Tool blocked: {verdict.get('reason', 'No reason given')}",
                    "is_error": True,
                })
                continue
            
            # 执行工具
            tool = self.tools.get(tool_name)
            if not tool:
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use_id,
                    "content": f"Tool not found: {tool_name}",
                    "is_error": True,
                })
                continue
            
            try:
                # 执行工具（异步）
                result = await tool.execute(**tool_input)
                result_str = str(result)
                
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use_id,
                    "content": result_str,
                    "is_error": False,
                })
                
                # 触发 tool_result 钩子
                self.extension_manager.fire_tool_result(tool_name, result, False)
                
            except Exception as e:
                error_msg = f"Tool execution failed: {str(e)}"
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use_id,
                    "content": error_msg,
                    "is_error": True,
                })
                
                # 触发 tool_result 钩子
                self.extension_manager.fire_tool_result(tool_name, error_msg, True)
        
        return tool_results
    
    def _extract_text(self, content: list) -> str:
        """从内容中提取文本"""
        text_parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text_parts.append(block.get("text", ""))
        return "\n".join(text_parts)
