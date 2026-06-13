"""Builtin tool implementations with hardened safety checks."""

import asyncio
import subprocess
from pathlib import Path
from typing import Any

from ..util import PathSecurityError, resolve_in_workspace
from .types import Tool

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_OUTPUT_SIZE = 500 * 1024  # 500 KB


class ToolExecutionError(RuntimeError):
    """Raised when a tool fails in a user-visible way."""


async def read_file(file_path: str, cwd: str) -> str:
    """Read a file with safety checks and size limits."""
    try:
        resolved = resolve_in_workspace(cwd, file_path)
    except PathSecurityError as exc:
        raise ToolExecutionError(f"Path security violation: {exc}") from exc

    if not resolved.exists():
        raise ToolExecutionError(f"File not found: {file_path}")
    if not resolved.is_file():
        raise ToolExecutionError(f"Not a file: {file_path}")

    size = resolved.stat().st_size
    if size > MAX_FILE_SIZE:
        raise ToolExecutionError(
            f"File too large: {file_path} ({size} bytes, max {MAX_FILE_SIZE})"
        )

    try:
        content = resolved.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:  # noqa: BLE001
        raise ToolExecutionError(f"Failed to read {file_path}: {exc}") from exc

    return content


async def write_file(file_path: str, content: str, cwd: str) -> str:
    """Write a file with safety checks."""
    try:
        resolved = resolve_in_workspace(cwd, file_path)
    except PathSecurityError as exc:
        raise ToolExecutionError(f"Path security violation: {exc}") from exc

    if len(content) > MAX_FILE_SIZE:
        raise ToolExecutionError(
            f"Content too large ({len(content)} bytes, max {MAX_FILE_SIZE})"
        )

    try:
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(content, encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        raise ToolExecutionError(f"Failed to write {file_path}: {exc}") from exc

    return f"Written {len(content)} bytes to {file_path}"


async def edit_file(file_path: str, old_text: str, new_text: str, cwd: str) -> str:
    """Edit a file by replacing old_text with new_text (first occurrence only)."""
    try:
        resolved = resolve_in_workspace(cwd, file_path)
    except PathSecurityError as exc:
        raise ToolExecutionError(f"Path security violation: {exc}") from exc

    if not resolved.exists():
        raise ToolExecutionError(f"File not found: {file_path}")

    try:
        content = resolved.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:  # noqa: BLE001
        raise ToolExecutionError(f"Failed to read {file_path}: {exc}") from exc

    if old_text not in content:
        raise ToolExecutionError(
            f"old_text not found in {file_path}. "
            "Ensure exact match including whitespace and newlines."
        )

    count = content.count(old_text)
    if count > 1:
        raise ToolExecutionError(
            f"old_text appears {count} times in {file_path}. "
            "Provide a unique match to avoid ambiguity."
        )

    new_content = content.replace(old_text, new_text, 1)

    try:
        resolved.write_text(new_content, encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        raise ToolExecutionError(f"Failed to write {file_path}: {exc}") from exc

    return f"Edited {file_path}: replaced {len(old_text)} chars with {len(new_text)} chars"


async def apply_patch(file_path: str, patch: str, cwd: str) -> str:
    """Apply a unified diff patch to a file.

    The patch should be in unified diff format. This is safer than full-file
    rewrites for small changes.
    """
    try:
        resolved = resolve_in_workspace(cwd, file_path)
    except PathSecurityError as exc:
        raise ToolExecutionError(f"Path security violation: {exc}") from exc

    if not resolved.exists():
        raise ToolExecutionError(f"File not found: {file_path}")

    # Write patch to a temp file and use `patch` command.
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".patch", delete=False) as tmp:
        tmp.write(patch)
        tmp_path = tmp.name

    try:
        proc = await asyncio.create_subprocess_exec(
            "patch",
            str(resolved),
            tmp_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=10)
        Path(tmp_path).unlink(missing_ok=True)

        if proc.returncode != 0:
            error_output = stderr.decode("utf-8", errors="replace")
            raise ToolExecutionError(f"Patch failed: {error_output}")

        return f"Applied patch to {file_path}"
    except asyncio.TimeoutError as exc:
        Path(tmp_path).unlink(missing_ok=True)
        raise ToolExecutionError("Patch command timed out") from exc
    except Exception as exc:  # noqa: BLE001
        Path(tmp_path).unlink(missing_ok=True)
        raise ToolExecutionError(f"Patch execution failed: {exc}") from exc


async def git_diff(cwd: str, file_path: str | None = None) -> str:
    """Show git diff of working tree changes.

    Args:
        cwd: Workspace root.
        file_path: Optional specific file to diff (relative to cwd).
    """
    args = ["git", "diff"]
    if file_path:
        try:
            resolved = resolve_in_workspace(cwd, file_path)
            args.append(str(resolved))
        except PathSecurityError as exc:
            raise ToolExecutionError(f"Path security violation: {exc}") from exc

    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=10)

        if proc.returncode != 0:
            error_output = stderr.decode("utf-8", errors="replace")
            raise ToolExecutionError(f"git diff failed: {error_output}")

        output = stdout.decode("utf-8", errors="replace")
        if len(output) > MAX_OUTPUT_SIZE:
            output = output[:MAX_OUTPUT_SIZE] + "\n... (truncated)"
        return output if output else "(no changes)"
    except asyncio.TimeoutError as exc:
        raise ToolExecutionError("git diff timed out") from exc
    except Exception as exc:  # noqa: BLE001
        raise ToolExecutionError(f"git diff failed: {exc}") from exc


async def run_bash(command: str, cwd: str, timeout_ms: int = 120000) -> str:
    """Run a bash command with timeout and output truncation.

    Returns a JSON-compatible dict with exit_code, stdout, stderr, timed_out, duration_ms.
    On success, returns stdout as a string for backward compatibility.
    On failure, raises ToolExecutionError with structured details.
    """
    import time

    timeout_sec = timeout_ms / 1000
    start = time.time()

    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=timeout_sec
            )
            duration_ms = int((time.time() - start) * 1000)

            stdout = stdout_bytes.decode("utf-8", errors="replace")
            stderr = stderr_bytes.decode("utf-8", errors="replace")

            # Truncate very large output.
            if len(stdout) > MAX_OUTPUT_SIZE:
                stdout = stdout[:MAX_OUTPUT_SIZE] + "\n... (stdout truncated)"
            if len(stderr) > MAX_OUTPUT_SIZE:
                stderr = stderr[:MAX_OUTPUT_SIZE] + "\n... (stderr truncated)"

            # On non-zero exit, raise an error with details.
            if proc.returncode != 0:
                combined = f"Command failed (exit {proc.returncode}):\n{stderr}\n{stdout}"
                raise ToolExecutionError(combined)

            # Success: return stdout only for backward compat.
            return stdout

        except asyncio.TimeoutError as exc:
            proc.kill()
            await proc.wait()
            duration_ms = int((time.time() - start) * 1000)
            raise ToolExecutionError(
                f"Command timed out after {timeout_ms}ms: {command}"
            ) from exc

    except ToolExecutionError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise ToolExecutionError(f"Command execution failed: {exc}") from exc


def create_builtin_tools(cwd: str, timeout_ms: int = 120000) -> list[Tool]:
    """Create the builtin tool set with hardened safety checks."""

    async def read_wrapper(file_path: str) -> str:
        return await read_file(file_path, cwd)

    async def write_wrapper(file_path: str, content: str) -> str:
        return await write_file(file_path, content, cwd)

    async def edit_wrapper(file_path: str, old_text: str, new_text: str) -> str:
        return await edit_file(file_path, old_text, new_text, cwd)

    async def patch_wrapper(file_path: str, patch: str) -> str:
        return await apply_patch(file_path, patch, cwd)

    async def git_diff_wrapper(file_path: str | None = None) -> str:
        return await git_diff(cwd, file_path)

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
            description="Edit a file by replacing old_text with new_text (first occurrence only)",
            parameters={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path to the file"},
                    "old_text": {"type": "string", "description": "Text to replace (must be unique)"},
                    "new_text": {"type": "string", "description": "Replacement text"},
                },
                "required": ["file_path", "old_text", "new_text"],
            },
            execute=edit_wrapper,
        ),
        Tool(
            name="apply_patch",
            description="Apply a unified diff patch to a file",
            parameters={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path to the file"},
                    "patch": {"type": "string", "description": "Unified diff patch"},
                },
                "required": ["file_path", "patch"],
            },
            execute=patch_wrapper,
        ),
        Tool(
            name="git_diff",
            description="Show git diff of working tree changes",
            parameters={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Optional: specific file to diff",
                    }
                },
            },
            execute=git_diff_wrapper,
        ),
        Tool(
            name="bash",
            description="Execute a bash command (with timeout and output limits)",
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
