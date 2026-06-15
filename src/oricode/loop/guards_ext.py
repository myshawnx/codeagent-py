"""循环护栏扩展集成"""

from ..runtime.extensions import Extension, ExtensionAPI
from .guards import (
    should_block_tool_call,
    should_soft_stop_on_failure,
    update_state_after_message,
    update_state_after_tool_call,
    update_state_after_tool_result,
)
from .types import LoopGuardOptions, LoopGuardState


class LoopGuardsExtension(Extension):
    """循环护栏扩展"""
    
    def __init__(self, options: LoopGuardOptions):
        self.options = options
        self.state = LoopGuardState(goal=options.goal)
    
    def on_session_start(self, api: ExtensionAPI) -> None:
        """会话开始时重置状态"""
        self.state = LoopGuardState(goal=self.options.goal)
        api.append_entry("loop-guard-start", {
            "max_tool_calls": self.options.max_tool_calls,
            "token_budget": self.options.token_budget,
        })
    
    def on_tool_call(self, api: ExtensionAPI, tool_name: str, tool_input: dict) -> dict | None:
        """工具调用前检查"""
        # 检查是否应该阻止
        should_block, reason = should_block_tool_call(
            self.state,
            self.options,
            tool_name,
            tool_input,
        )
        
        if should_block:
            api.append_entry("loop-guard-block", {
                "tool": tool_name,
                "reason": reason,
            })
            return {"block": True, "reason": reason}
        
        # 更新状态
        self.state = update_state_after_tool_call(self.state)
        
        return None
    
    def on_tool_result(self, api: ExtensionAPI, tool_name: str, result: any, is_error: bool) -> None:
        """工具结果后检查"""
        # 构造结果字典
        tool_result = {
            "content": [{"type": "text", "text": str(result)}],
            "is_error": is_error,
        }
        
        # 更新状态
        self.state = update_state_after_tool_result(self.state, tool_result)
        
        # 检查是否应该软停止
        should_stop, reason = should_soft_stop_on_failure(
            self.state,
            self.options,
            tool_result,
        )
        
        if should_stop:
            api.append_entry("loop-guard-soft-stop", {
                "reason": reason,
            })
            # 软停止：记录但不阻止（让 agent 自己处理）
    
    def on_message_end(self, api: ExtensionAPI, usage: dict) -> None:
        """消息结束后更新 token 统计"""
        tokens_used = usage.get("output_tokens", 0) + usage.get("input_tokens", 0)
        
        self.state = update_state_after_message(
            self.state,
            self.options,
            tokens_used,
        )
        
        api.append_entry("loop-guard-token-usage", {
            "total_tokens": self.state.total_tokens,
            "token_budget": self.options.token_budget,
            "exceeded": self.state.token_budget_exceeded,
        })
