"""配置写入器 - 写入 .agent/ 目录"""

import json
from pathlib import Path

from .schema import PolicyConfig, ProjectProfile


def get_agent_dir(cwd: str) -> Path:
    """获取 .agent 目录路径"""
    return Path(cwd) / ".agent"


def ensure_agent_dir(cwd: str) -> Path:
    """确保 .agent 目录存在"""
    agent_dir = get_agent_dir(cwd)
    agent_dir.mkdir(parents=True, exist_ok=True)
    return agent_dir


def write_json_file(path: Path, data: dict) -> None:
    """写入 JSON 文件"""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def write_policy_config(cwd: str, policy: PolicyConfig) -> None:
    """写入策略配置"""
    agent_dir = ensure_agent_dir(cwd)
    policy_path = agent_dir / "policy.json"
    
    data = policy.model_dump(exclude_none=True)
    write_json_file(policy_path, data)


def write_project_profile(cwd: str, profile: ProjectProfile) -> None:
    """写入项目画像"""
    agent_dir = ensure_agent_dir(cwd)
    profile_path = agent_dir / "project-profile.json"
    
    data = profile.model_dump(exclude_none=True)
    write_json_file(profile_path, data)


def write_memory(cwd: str, content: str) -> None:
    """写入记忆文件"""
    agent_dir = ensure_agent_dir(cwd)
    memory_path = agent_dir / "memory.md"
    
    memory_path.write_text(content, encoding="utf-8")


def append_memory(cwd: str, content: str) -> None:
    """追加记忆内容"""
    agent_dir = ensure_agent_dir(cwd)
    memory_path = agent_dir / "memory.md"
    
    existing = ""
    if memory_path.exists():
        existing = memory_path.read_text(encoding="utf-8")
    
    new_content = existing + "\n\n" + content if existing else content
    memory_path.write_text(new_content, encoding="utf-8")
