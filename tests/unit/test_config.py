"""配置加载和保存测试"""

from pathlib import Path

import pytest

from codeagent.config.loader import load_agent_config, load_policy_config, load_project_profile
from codeagent.config.schema import PolicyConfig, ProjectProfile, LimitsConfig
from codeagent.config.writer import write_policy_config, write_project_profile


class TestConfigLoader:
    """配置加载测试"""
    
    def test_load_empty_config(self, temp_repo):
        """加载空配置返回默认值"""
        config = load_agent_config(temp_repo)
        assert config.policy is not None
        assert config.profile is None
    
    def test_load_nonexistent_profile(self, temp_repo):
        """加载不存在的 profile 返回 None"""
        profile = load_project_profile(temp_repo)
        assert profile is None


class TestConfigWriter:
    """配置写入测试"""
    
    def test_write_and_load_policy(self, temp_repo):
        """写入并加载策略配置"""
        policy = PolicyConfig(
            limits=LimitsConfig(max_tool_calls=200, token_budget=100000)
        )
        
        write_policy_config(temp_repo, policy)
        loaded = load_policy_config(temp_repo)
        
        assert loaded.limits.max_tool_calls == 200
        assert loaded.limits.token_budget == 100000
    
    def test_write_and_load_profile(self, temp_repo):
        """写入并加载项目画像"""
        profile = ProjectProfile(
            language="python",
            package_manager="uv",
            source_dirs=["src"],
            test_dirs=["tests"],
            commands={"test": "pytest"},
        )
        
        write_project_profile(temp_repo, profile)
        loaded = load_project_profile(temp_repo)
        
        assert loaded.language == "python"
        assert loaded.package_manager == "uv"
        assert loaded.commands["test"] == "pytest"
    
    def test_agent_dir_created(self, temp_repo):
        """确保 .agent 目录被创建"""
        profile = ProjectProfile(language="python", package_manager="pip")
        write_project_profile(temp_repo, profile)
        
        agent_dir = Path(temp_repo) / ".agent"
        assert agent_dir.exists()
        assert agent_dir.is_dir()
