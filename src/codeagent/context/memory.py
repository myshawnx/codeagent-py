"""记忆文件管理"""

from pathlib import Path


def read_memory(cwd: str) -> str:
    """读取记忆文件"""
    memory_path = Path(cwd) / ".agent" / "memory.md"
    if memory_path.exists():
        return memory_path.read_text(encoding="utf-8")
    return ""


def write_memory(cwd: str, content: str) -> None:
    """写入记忆文件"""
    agent_dir = Path(cwd) / ".agent"
    agent_dir.mkdir(parents=True, exist_ok=True)
    
    memory_path = agent_dir / "memory.md"
    memory_path.write_text(content, encoding="utf-8")


def append_memory(cwd: str, content: str) -> None:
    """追加记忆内容"""
    existing = read_memory(cwd)
    
    if existing:
        new_content = f"{existing}\n\n{content}"
    else:
        new_content = content
    
    write_memory(cwd, new_content)


def render_memory_for_prompt(memory: str) -> str:
    """渲染记忆为系统提示"""
    if not memory:
        return ""
    
    return f"""# Project Memory

{memory}
"""
