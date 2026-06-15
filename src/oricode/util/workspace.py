"""Workspace path safety utilities.

All file operations must go through :func:`resolve_in_workspace` to prevent
path traversal, symlink escape, and writes outside the workspace root.
"""

from __future__ import annotations

import os
from pathlib import Path


class PathSecurityError(RuntimeError):
    """Raised when a path operation violates workspace boundaries."""


def resolve_in_workspace(workspace_root: str, user_path: str) -> Path:
    """Resolve ``user_path`` within ``workspace_root`` with security checks.

    Returns the canonical absolute path if safe; raises :class:`PathSecurityError`
    otherwise.

    Prevents:
      - ``../`` escaping the workspace
      - Absolute paths outside the workspace
      - Symlink escape (a symlink pointing outside the workspace)

    Args:
        workspace_root: The trusted workspace directory (must exist).
        user_path: The user-provided path (relative or absolute).

    Raises:
        PathSecurityError: If the resolved path is outside the workspace.

    Example:
        >>> root = "/home/user/project"
        >>> resolve_in_workspace(root, "src/main.py")
        PosixPath('/home/user/project/src/main.py')
        >>> resolve_in_workspace(root, "../etc/passwd")
        PathSecurityError: Path escapes workspace
    """
    workspace = Path(workspace_root).resolve(strict=True)

    # Treat relative paths as relative to workspace_root.
    if not os.path.isabs(user_path):
        candidate = workspace / user_path
    else:
        candidate = Path(user_path)

    # Resolve to canonical form, following symlinks.
    # strict=False allows non-existent files (we may be about to create them).
    try:
        resolved = candidate.resolve(strict=False)
    except (OSError, RuntimeError) as exc:
        raise PathSecurityError(f"Cannot resolve path: {user_path}") from exc

    # Verify the resolved path is still inside the workspace.
    try:
        resolved.relative_to(workspace)
    except ValueError as exc:
        raise PathSecurityError(
            f"Path escapes workspace: {user_path} -> {resolved}"
        ) from exc

    return resolved


def is_protected_filename(path: Path) -> bool:
    """Check if a file is in a small protected set (e.g. .env, .ssh/*).

    This is a fast runtime check separate from the glob-based policy engine.
    """
    name = path.name
    parts = path.parts

    # Common sensitive files.
    if name in {".env", ".env.local", ".env.production"}:
        return True
    if name.endswith((".key", ".pem", ".crt", ".p12", ".pfx")):
        return True
    if any(p == ".ssh" for p in parts):
        return True
    if any(p == ".git" and name == "config" for p in parts):
        return True

    return False
