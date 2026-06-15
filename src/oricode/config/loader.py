"""配置加载器 - 从 .agent/ 目录读取配置"""

import json
from pathlib import Path
from typing import Any

from .schema import AgentConfig, PolicyConfig, ProjectProfile


def get_agent_dir(cwd: str) -> Path:
    """获取 .agent 目录路径"""
    return Path(cwd) / ".agent"


def load_json_file(path: Path) -> dict[str, Any] | None:
    """加载 JSON 文件"""
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def load_policy_config(cwd: str) -> PolicyConfig:
    """加载策略配置"""
    agent_dir = get_agent_dir(cwd)
    policy_path = agent_dir / "policy.json"
    
    data = load_json_file(policy_path)
    if data:
        return PolicyConfig.model_validate(data)
    
    return PolicyConfig()


def load_project_profile(cwd: str) -> ProjectProfile | None:
    """加载项目画像"""
    agent_dir = get_agent_dir(cwd)
    profile_path = agent_dir / "project-profile.json"
    
    data = load_json_file(profile_path)
    if data:
        return ProjectProfile.model_validate(data)
    
    return None


def load_agent_config(cwd: str) -> AgentConfig:
    """加载完整的 Agent 配置"""
    policy = load_policy_config(cwd)
    profile = load_project_profile(cwd)
    
    return AgentConfig(policy=policy, profile=profile)


def load_memory(cwd: str) -> str:
    """加载记忆文件内容"""
    agent_dir = get_agent_dir(cwd)
    memory_path = agent_dir / "memory.md"
    
    if memory_path.exists():
        return memory_path.read_text(encoding="utf-8")
    
    return ""
