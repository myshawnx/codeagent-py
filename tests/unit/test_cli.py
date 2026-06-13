"""CLI 命令测试"""

from pathlib import Path

import pytest

from codeagent.cli.commands.init import run_init


class TestInitCommand:
    """init 命令测试"""
    
    def test_init_creates_agent_dir(self, temp_repo, monkeypatch, capsys):
        """测试 init 创建 .agent 目录"""
        monkeypatch.chdir(temp_repo)
        
        run_init(force=False)
        
        agent_dir = Path(temp_repo) / ".agent"
        assert agent_dir.exists()
        assert (agent_dir / "policy.json").exists()
        assert (agent_dir / "project-profile.json").exists()
        assert (agent_dir / "memory.md").exists()
    
    def test_init_force_overwrites(self, temp_repo, monkeypatch):
        """测试 --force 覆盖现有配置"""
        monkeypatch.chdir(temp_repo)
        
        # 第一次初始化
        run_init(force=False)
        
        # 修改配置
        policy_path = Path(temp_repo) / ".agent" / "policy.json"
        original_content = policy_path.read_text()
        policy_path.write_text('{"modified": true}')
        
        # 强制重新初始化
        run_init(force=True)
        
        # 验证被覆盖
        new_content = policy_path.read_text()
        assert new_content != '{"modified": true}'
        assert "limits" in new_content  # 默认配置应该有 limits
