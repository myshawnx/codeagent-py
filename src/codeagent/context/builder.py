"""Context builder for agent sessions.

Assembles the system prompt by loading project instructions (AGENTS.md, CLAUDE.md,
.agent/instructions.md) with precedence rules, injecting project profile context,
and applying token-aware trimming.
"""

from __future__ import annotations

from pathlib import Path

from ..config.schema import ProjectProfile


def load_project_instructions(cwd: str) -> str | None:
    """Load project instructions with precedence rules.

    Precedence (first found wins):
    1. .agent/instructions.md
    2. AGENTS.md
    3. CLAUDE.md

    Returns None if no instructions found.
    """
    root = Path(cwd)
    candidates = [
        root / ".agent" / "instructions.md",
        root / "AGENTS.md",
        root / "CLAUDE.md",
    ]

    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            try:
                return candidate.read_text(encoding="utf-8")
            except Exception:  # noqa: BLE001
                continue

    return None


def render_profile_context(profile: ProjectProfile | None) -> str:
    """Render project profile as context snippet."""
    if not profile or profile.language == "unknown":
        return ""

    lines = ["# Project Context"]
    lines.append(f"- Language: {profile.language}")
    lines.append(f"- Package Manager: {profile.package_manager}")

    if profile.framework:
        lines.append(f"- Framework: {profile.framework}")
    if profile.test_framework:
        lines.append(f"- Test Framework: {profile.test_framework}")

    if profile.commands:
        lines.append("\nCommon commands:")
        for name, cmd in profile.commands.items():
            lines.append(f"  - {name}: `{cmd}`")

    return "\n".join(lines)


def build_system_prompt(
    base_prompt: str,
    profile: ProjectProfile | None = None,
    project_instructions: str | None = None,
    max_tokens: int | None = None,
) -> str:
    """Build the final system prompt.

    Combines:
    1. Base prompt (agent identity/guidelines)
    2. Project profile context (language, tools, commands)
    3. Project instructions (if present)

    Args:
        base_prompt: Core agent system prompt.
        profile: Detected project profile (optional).
        project_instructions: Loaded from AGENTS.md/etc (optional).
        max_tokens: Token budget for system prompt (optional, for future trimming).

    Returns:
        Complete system prompt string.
    """
    sections = [base_prompt]

    # Add profile context if available.
    if profile:
        profile_ctx = render_profile_context(profile)
        if profile_ctx:
            sections.append(profile_ctx)

    # Add project instructions if present.
    if project_instructions:
        sections.append("# Project Instructions")
        sections.append(project_instructions.strip())

    combined = "\n\n".join(sections)

    # Token-aware trimming: if max_tokens is set and exceeded, trim instructions.
    # For now, this is a placeholder - full implementation would use tiktoken or similar.
    if max_tokens:
        # Simple char-based approximation: ~4 chars per token.
        approx_tokens = len(combined) // 4
        if approx_tokens > max_tokens:
            # Trim from the end of project instructions (least critical).
            char_limit = max_tokens * 4
            combined = combined[:char_limit] + "\n\n[... instructions truncated ...]"

    return combined
