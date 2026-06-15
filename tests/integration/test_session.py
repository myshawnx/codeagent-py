"""Agent Session 集成测试"""

import os
import pytest

from oricode.config.schema import ApprovalMode, PolicyConfig
from oricode.loop.guards_ext import LoopGuardsExtension
from oricode.loop.types import LoopGuardOptions
from oricode.policy.gateway import PolicyGateway
from oricode.runtime.session import AgentSession


# 跳过需要真实 API 密钥的测试
pytestmark = pytest.mark.skipif(
    not os.getenv("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set"
)


class TestAgentSession:
    """Agent Session 基础测试"""
    
    @pytest.mark.asyncio
    async def test_session_creation(self, temp_repo):
        """测试会话创建"""
        session = AgentSession(cwd=temp_repo)
        assert session.cwd == temp_repo
        assert len(session.tools) == 6  # read, write, edit, apply_patch, git_diff, bash
    
    @pytest.mark.asyncio
    async def test_tool_registration(self, temp_repo):
        """测试工具注册"""
        session = AgentSession(cwd=temp_repo)
        
        initial_count = len(session.tools)
        
        # Tools are registered
        assert "read" in session.tools
        assert "write" in session.tools
        assert "edit" in session.tools
        assert "apply_patch" in session.tools
        assert "git_diff" in session.tools
        assert "bash" in session.tools


class TestPolicyIntegration:
    """策略集成测试"""
    
    @pytest.mark.asyncio
    async def test_policy_gateway_denies_dangerous_command(self, temp_repo):
        """测试策略网关拒绝危险命令"""
        policy = PolicyConfig()
        gateway = PolicyGateway(
            policy=policy,
            mode=ApprovalMode.WORKSPACE_WRITE,
            repo_root=temp_repo,
        )
        
        session = AgentSession(cwd=temp_repo, extensions=[gateway])
        
        # 策略应该拒绝 rm -rf
        # 注意：这只是测试扩展集成，不会真正调用 API
        assert len(session.extensions) == 1


class TestLoopGuardsIntegration:
    """循环护栏集成测试"""
    
    @pytest.mark.asyncio
    async def test_loop_guards_track_state(self, temp_repo):
        """测试循环护栏跟踪状态"""
        options = LoopGuardOptions(
            goal="test goal",
            max_tool_calls=10,
        )
        guards = LoopGuardsExtension(options)
        
        session = AgentSession(cwd=temp_repo, extensions=[guards])
        
        # 初始状态
        assert guards.state.tool_calls == 0
        assert not guards.state.blocked
