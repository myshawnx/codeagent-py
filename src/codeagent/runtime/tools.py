"""内置工具实现"""

import asyncio
import subprocess
from pathlib import Path
from typing import Any

from .types import Tool


async def read_file(file_path: str, cwd: str) -> str:
    """读取文件"""
    path = Path(cwd) / file_path
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    return path.read_text(encoding="utf-8")


async def write_file(file_path: str, content: str, cwd: str) -> str:
    """写入文件"""
    path = Path(cwd) / file_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return f"Written {len(content)} bytes to {file_path}"


async def edit_file(file_path: str, old_text: str, new_text: str, cwd: str) -> str:
    """编辑文件"""
    path = Path(cwd) / file_path
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    content = path.read_text(encoding="utf-8")
    
    if old_text not in content:
        raise ValueError(f"old_text not found in {file_path}")
    
    # 只替换第一次出现
    new_content = content.replace(old_text, new_text, 1)
    path.write_text(new_content, encoding="utf-8")
    
    return f"Edited {file_path}"


async def run_bash(command: str, cwd: str, timeout_ms: int = 120000) -> str:
    """运行 bash 命令"""
    timeout_sec = timeout_ms / 1000
    
    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=cwd,
        )
        
        try:
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout_sec)
            return stdout.decode("utf-8", errors="replace")
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise ValueError(f"Command timeout after {timeout_ms}ms: {command}")
            
    except Exception as e:
        raise ValueError(f"Command failed: {e}")


def create_builtin_tools(cwd: str, timeout_ms: int = 120000) -> list[Tool]:
    """创建内置工具"""
    
    async def read_wrapper(file_path: str) -> str:
        return await read_file(file_path, cwd)
    
    async def write_wrapper(file_path: str, content: str) -> str:
        return await write_file(file_path, content, cwd)
    
    async def edit_wrapper(file_path: str, old_text: str, new_text: str) -> str:
        return await edit_file(file_path, old_text, new_text, cwd)
    
    async def bash_wrapper(command: str) -> str:
        return await run_bash(command, cwd, timeout_ms)
    
    return [
        Tool(
            name="read",
            description="Read the contents of a file",
            parameters={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path to the file"}
                },
                "required": ["file_path"],
            },
            execute=read_wrapper,
        ),
        Tool(
            name="write",
            description="Write content to a file",
            parameters={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path to the file"},
                    "content": {"type": "string", "description": "Content to write"},
                },
                "required": ["file_path", "content"],
            },
            execute=write_wrapper,
        ),
        Tool(
            name="edit",
            description="Edit a file by replacing old_text with new_text",
            parameters={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path to the file"},
                    "old_text": {"type": "string", "description": "Text to replace"},
                    "new_text": {"type": "string", "description": "Replacement text"},
                },
                "required": ["file_path", "old_text", "new_text"],
            },
            execute=edit_wrapper,
        ),
        Tool(
            name="bash",
            description="Execute a bash command",
            parameters={
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Command to execute"}
                },
                "required": ["command"],
            },
            execute=bash_wrapper,
        ),
    ]
