"""循环护栏逻辑（纯函数版本，P1 会添加扩展集成）"""

from .failure import create_failure_signature
from .testfile import allows_test_writes, is_test_file, is_test_fix_goal
from .types import LoopGuardOptions, LoopGuardState


def should_block_tool_call(
    state: LoopGuardState,
    options: LoopGuardOptions,
    tool_name: str,
    tool_input: dict,
) -> tuple[bool, str | None]:
    """
    检查是否应该阻止工具调用
    
    返回: (should_block, reason)
    """
    # Token 预算检查
    if state.token_budget_exceeded:
        return True, f"Token budget exceeded ({options.token_budget})"
    
    # 工具调用次数检查
    if state.tool_calls >= options.max_tool_calls:
        return True, f"Tool calls limit reached ({options.max_tool_calls})"
    
    # 反作弊检查：修复测试任务中禁止修改测试文件
    if tool_name in ["write", "edit", "apply_patch"]:
        if is_test_fix_goal(state.goal) and not allows_test_writes(state.goal):
            file_path = tool_input.get("file_path") or tool_input.get("target")
            if file_path and is_test_file(file_path, options.profile):
                return True, f"Reward-hacking guard: blocked write to test file: {file_path}"
    
    return False, None


def should_soft_stop_on_failure(
    state: LoopGuardState,
    options: LoopGuardOptions,
    tool_result: dict,
) -> tuple[bool, str | None]:
    """
    检查是否应该在测试失败时软停止
    
    返回: (should_stop, reason)
    """
    # 检查是否是测试失败
    signature_data = create_failure_signature(tool_result)
    if not signature_data:
        return False, None
    
    signature = signature_data["signature"]
    
    # 检查是否是重复失败
    if signature == state.last_failure_signature:
        if state.repeated_failures >= options.max_fix_iterations:
            return True, f"Same test failure repeated {state.repeated_failures} times with no progress"
    
    return False, None


def update_state_after_tool_call(state: LoopGuardState) -> LoopGuardState:
    """工具调用后更新状态"""
    return state.model_copy(update={"tool_calls": state.tool_calls + 1})


def update_state_after_tool_result(
    state: LoopGuardState,
    tool_result: dict,
) -> LoopGuardState:
    """工具结果后更新状态"""
    signature_data = create_failure_signature(tool_result)
    
    if not signature_data:
        # 成功或非测试，重置失败计数
        return state.model_copy(
            update={
                "last_failure_signature": None,
                "repeated_failures": 0,
            }
        )
    
    signature = signature_data["signature"]
    
    if signature == state.last_failure_signature:
        # 相同失败
        return state.model_copy(
            update={"repeated_failures": state.repeated_failures + 1}
        )
    else:
        # 新失败
        return state.model_copy(
            update={
                "last_failure_signature": signature,
                "repeated_failures": 1,
            }
        )


def update_state_after_message(
    state: LoopGuardState,
    options: LoopGuardOptions,
    tokens_used: int,
) -> LoopGuardState:
    """消息完成后更新状态"""
    new_total = state.total_tokens + tokens_used
    
    updates = {"total_tokens": new_total}
    
    # 检查是否超出预算
    if options.token_budget and new_total >= options.token_budget:
        updates["token_budget_exceeded"] = True
    
    return state.model_copy(update=updates)
