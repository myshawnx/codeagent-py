"""循环护栏单元测试"""

import pytest

from oricode.config.schema import ProjectProfile
from oricode.loop.guards import (
    should_block_tool_call,
    should_soft_stop_on_failure,
    update_state_after_tool_call,
    update_state_after_tool_result,
    update_state_after_message,
)
from oricode.loop.types import LoopGuardOptions, LoopGuardState


@pytest.fixture
def options():
    """循环护栏选项"""
    profile = ProjectProfile(
        language="python",
        package_manager="uv",
        test_dirs=["tests"],
        source_dirs=["src"],
        commands={"test": "pytest"},
    )
    return LoopGuardOptions(
        goal="Fix the bug in main.py",
        max_tool_calls=100,
        max_fix_iterations=3,
        token_budget=50000,
        profile=profile,
    )


@pytest.fixture
def state():
    """初始状态"""
    return LoopGuardState(
        goal="Fix the bug in main.py",
        tool_calls=0,
        total_tokens=0,
    )


class TestToolCallLimits:
    """工具调用限制测试"""
    
    def test_within_limit(self, state, options):
        """在限制内不阻止"""
        should_block, reason = should_block_tool_call(state, options, "read", {})
        assert not should_block
        assert reason is None
    
    def test_exceed_limit(self, state, options):
        """超出限制时阻止"""
        state_exceeded = state.model_copy(update={"tool_calls": 100})
        should_block, reason = should_block_tool_call(state_exceeded, options, "read", {})
        assert should_block
        assert "limit reached" in reason.lower()
    
    def test_token_budget_exceeded(self, state, options):
        """Token 预算超出时阻止"""
        state_exceeded = state.model_copy(update={"token_budget_exceeded": True})
        should_block, reason = should_block_tool_call(state_exceeded, options, "read", {})
        assert should_block
        assert "budget exceeded" in reason.lower()


class TestRewardHackingGuard:
    """反作弊护栏测试"""
    
    def test_block_test_file_write_in_fix_goal(self, state, options):
        """修复任务中阻止修改测试文件"""
        state_fix = state.model_copy(update={"goal": "fix test that is failing"})
        should_block, reason = should_block_tool_call(
            state_fix,
            options,
            "write",
            {"file_path": "tests/test_main.py"},
        )
        assert should_block
        assert "Reward-hacking" in reason
    
    def test_allow_test_file_write_in_add_test_goal(self, state, options):
        """添加测试任务允许修改测试文件"""
        state_add = state.model_copy(update={"goal": "add test for the new feature"})
        should_block, reason = should_block_tool_call(
            state_add,
            options,
            "write",
            {"file_path": "tests/test_feature.py"},
        )
        assert not should_block
    
    def test_allow_source_file_write_in_fix_goal(self, state, options):
        """修复任务允许修改源码文件"""
        state_fix = state.model_copy(update={"goal": "fix test that is failing"})
        should_block, reason = should_block_tool_call(
            state_fix,
            options,
            "write",
            {"file_path": "src/main.py"},
        )
        assert not should_block


class TestFailureDetection:
    """失败检测测试"""
    
    def test_no_stop_on_first_failure(self, state, options):
        """首次失败不停止"""
        tool_result = {
            "content": [{"type": "text", "text": "FAILED tests/test_main.py::test_foo"}],
            "is_error": True,
        }
        should_stop, reason = should_soft_stop_on_failure(state, options, tool_result)
        assert not should_stop
    
    def test_stop_on_repeated_failure(self, state, options):
        """重复失败时停止"""
        # 模拟相同失败重复 3 次
        tool_result = {
            "content": [{"type": "text", "text": "FAILED tests/test_main.py::test_foo"}],
            "is_error": True,
        }
        
        state1 = update_state_after_tool_result(state, tool_result)
        should_stop, _ = should_soft_stop_on_failure(state1, options, tool_result)
        assert not should_stop  # 第 1 次
        
        state2 = update_state_after_tool_result(state1, tool_result)
        should_stop, _ = should_soft_stop_on_failure(state2, options, tool_result)
        assert not should_stop  # 第 2 次
        
        state3 = update_state_after_tool_result(state2, tool_result)
        should_stop, reason = should_soft_stop_on_failure(state3, options, tool_result)
        assert should_stop  # 第 3 次，达到 max_fix_iterations
        assert "no progress" in reason.lower()
    
    def test_reset_on_different_failure(self, state, options):
        """不同失败重置计数"""
        result1 = {
            "content": [{"type": "text", "text": "FAILED tests/test_a.py::test_foo"}],
            "is_error": True,
        }
        result2 = {
            "content": [{"type": "text", "text": "FAILED tests/test_b.py::test_bar"}],
            "is_error": True,
        }
        
        state1 = update_state_after_tool_result(state, result1)
        assert state1.repeated_failures == 1
        
        state2 = update_state_after_tool_result(state1, result2)
        assert state2.repeated_failures == 1  # 重置为 1（不同失败）


class TestTokenBudget:
    """Token 预算测试"""
    
    def test_track_token_usage(self, state, options):
        """跟踪 token 使用"""
        state1 = update_state_after_message(state, options, 10000)
        assert state1.total_tokens == 10000
        assert not state1.token_budget_exceeded
        
        state2 = update_state_after_message(state1, options, 20000)
        assert state2.total_tokens == 30000
        assert not state2.token_budget_exceeded
        
        state3 = update_state_after_message(state2, options, 25000)
        assert state3.total_tokens == 55000
        assert state3.token_budget_exceeded  # 超过 50000
    
    def test_no_budget_limit(self, state):
        """没有预算限制时不触发"""
        options_no_budget = LoopGuardOptions(
            goal="test",
            max_tool_calls=100,
            token_budget=None,  # 无限制
        )
        
        state1 = update_state_after_message(state, options_no_budget, 100000)
        assert state1.total_tokens == 100000
        assert not state1.token_budget_exceeded
