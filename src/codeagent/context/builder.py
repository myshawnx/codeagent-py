"""Context builder for agent sessions.

Assembles the system prompt by loading project instructions (AGENTS.md, CLAUDE.md,
.agent/instructions.md) with precedence rules, injecting project profile context,
and applying token-aware trimming.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path

from ..config.schema import ProjectProfile
from ..providers import (
    ModelMessage,
    ModelProvider,
    ModelRequest,
    TokenCount,
    count_tokens_with_fallback,
    estimate_model_request_tokens,
)

TRUNCATION_NOTICE = "[... instructions truncated ...]"
TokenCounter = Callable[[str], TokenCount]
AsyncTokenCounter = Callable[[str], Awaitable[TokenCount]]


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


def estimate_system_prompt_tokens(prompt: str) -> TokenCount:
    """Fallback system-prompt token estimate, explicitly marked estimated."""
    request = ModelRequest(
        model="context-budget",
        messages=[ModelMessage(role="user", content=[{"type": "text", "text": ""}])],
        system=prompt,
        max_tokens=1,
    )
    return estimate_model_request_tokens(request, provider="context-estimator")


def _compose_prompt_parts(
    base_prompt: str,
    profile: ProjectProfile | None,
    project_instructions: str | None,
) -> tuple[list[str], str | None]:
    stable_sections = [base_prompt]

    if profile:
        profile_ctx = render_profile_context(profile)
        if profile_ctx:
            stable_sections.append(profile_ctx)

    instructions = project_instructions.strip() if project_instructions else None
    return stable_sections, instructions


def _join_prompt(stable_sections: list[str], instructions: str | None = None) -> str:
    sections = list(stable_sections)
    if instructions is not None:
        sections.append("# Project Instructions")
        sections.append(instructions)
    return "\n\n".join(section for section in sections if section)


def _truncated_instructions(instructions: str, char_count: int) -> str:
    prefix = instructions[:char_count].rstrip()
    if prefix:
        return f"{prefix}\n\n{TRUNCATION_NOTICE}"
    return TRUNCATION_NOTICE


def _trim_with_counter(
    stable_sections: list[str],
    instructions: str | None,
    max_tokens: int,
    token_counter: TokenCounter,
) -> str:
    prompt = _join_prompt(stable_sections, instructions)
    if token_counter(prompt).input_tokens <= max_tokens or instructions is None:
        return prompt

    best: str | None = None
    low = 0
    high = len(instructions)
    while low <= high:
        mid = (low + high) // 2
        candidate = _join_prompt(
            stable_sections,
            _truncated_instructions(instructions, mid),
        )
        if token_counter(candidate).input_tokens <= max_tokens:
            best = candidate
            low = mid + 1
        else:
            high = mid - 1

    if best is not None:
        return best

    # The stable prefix is more important than hitting the budget exactly.
    return _join_prompt(stable_sections, TRUNCATION_NOTICE)


async def _trim_with_async_counter(
    stable_sections: list[str],
    instructions: str | None,
    max_tokens: int,
    token_counter: AsyncTokenCounter,
) -> str:
    prompt = _join_prompt(stable_sections, instructions)
    if (await token_counter(prompt)).input_tokens <= max_tokens or instructions is None:
        return prompt

    best: str | None = None
    low = 0
    high = len(instructions)
    while low <= high:
        mid = (low + high) // 2
        candidate = _join_prompt(
            stable_sections,
            _truncated_instructions(instructions, mid),
        )
        if (await token_counter(candidate)).input_tokens <= max_tokens:
            best = candidate
            low = mid + 1
        else:
            high = mid - 1

    if best is not None:
        return best

    return _join_prompt(stable_sections, TRUNCATION_NOTICE)


def build_system_prompt(
    base_prompt: str,
    profile: ProjectProfile | None = None,
    project_instructions: str | None = None,
    max_tokens: int | None = None,
    token_counter: TokenCounter | None = None,
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
        max_tokens: Token budget for system prompt (optional).
        token_counter: Optional provider-backed or test token counter. If omitted,
            trimming uses an explicitly estimated fallback.

    Returns:
        Complete system prompt string.
    """
    stable_sections, instructions = _compose_prompt_parts(
        base_prompt,
        profile,
        project_instructions,
    )
    if max_tokens is None:
        return _join_prompt(stable_sections, instructions)

    return _trim_with_counter(
        stable_sections,
        instructions,
        max_tokens,
        token_counter or estimate_system_prompt_tokens,
    )


async def build_system_prompt_with_provider_budget(
    base_prompt: str,
    *,
    provider: ModelProvider,
    model: str,
    max_tokens: int,
    profile: ProjectProfile | None = None,
    project_instructions: str | None = None,
) -> str:
    """Build and trim a system prompt using provider-level token counting."""
    stable_sections, instructions = _compose_prompt_parts(
        base_prompt,
        profile,
        project_instructions,
    )

    async def count_prompt(prompt: str) -> TokenCount:
        request = ModelRequest(
            model=model,
            messages=[ModelMessage(role="user", content=[{"type": "text", "text": " "}])],
            system=prompt,
            max_tokens=1,
        )
        return await count_tokens_with_fallback(provider, request)

    return await _trim_with_async_counter(
        stable_sections,
        instructions,
        max_tokens,
        count_prompt,
    )
