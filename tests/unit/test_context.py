"""Tests for P3 context builder."""

from pathlib import Path

import pytest

from codeagent.config.schema import ProjectProfile
from codeagent.context import build_system_prompt, load_project_instructions, render_profile_context
from codeagent.providers import MockProvider, text_response
from codeagent.runtime.events import EventBus
from codeagent.runtime.session import AgentSession


class TestLoadProjectInstructions:
    """Test instruction loading with precedence."""

    def test_load_from_agent_dir(self, temp_repo):
        agent_dir = Path(temp_repo) / ".agent"
        agent_dir.mkdir(exist_ok=True)
        (agent_dir / "instructions.md").write_text("# Agent instructions")

        instructions = load_project_instructions(temp_repo)
        assert instructions == "# Agent instructions"

    def test_load_from_agents_md(self, temp_repo):
        (Path(temp_repo) / "AGENTS.md").write_text("# Agents file")

        instructions = load_project_instructions(temp_repo)
        assert instructions == "# Agents file"

    def test_load_from_claude_md(self, temp_repo):
        (Path(temp_repo) / "CLAUDE.md").write_text("# Claude file")

        instructions = load_project_instructions(temp_repo)
        assert instructions == "# Claude file"

    def test_precedence_agent_dir_wins(self, temp_repo):
        agent_dir = Path(temp_repo) / ".agent"
        agent_dir.mkdir(exist_ok=True)
        (agent_dir / "instructions.md").write_text("agent-dir")
        (Path(temp_repo) / "AGENTS.md").write_text("agents-md")
        (Path(temp_repo) / "CLAUDE.md").write_text("claude-md")

        instructions = load_project_instructions(temp_repo)
        assert instructions == "agent-dir"

    def test_precedence_agents_over_claude(self, temp_repo):
        (Path(temp_repo) / "AGENTS.md").write_text("agents-md")
        (Path(temp_repo) / "CLAUDE.md").write_text("claude-md")

        instructions = load_project_instructions(temp_repo)
        assert instructions == "agents-md"

    def test_no_instructions_returns_none(self, temp_repo):
        instructions = load_project_instructions(temp_repo)
        assert instructions is None


class TestRenderProfileContext:
    """Test profile context rendering."""

    def test_render_python_profile(self):
        profile = ProjectProfile(
            language="python",
            package_manager="uv",
            test_framework="pytest",
            commands={"test": "pytest", "lint": "ruff check"},
        )

        context = render_profile_context(profile)
        assert "Language: python" in context
        assert "Package Manager: uv" in context
        assert "Test Framework: pytest" in context
        assert "test: `pytest`" in context

    def test_unknown_profile_returns_empty(self):
        profile = ProjectProfile(language="unknown", package_manager="unknown")
        context = render_profile_context(profile)
        assert context == ""

    def test_none_profile_returns_empty(self):
        context = render_profile_context(None)
        assert context == ""


class TestBuildSystemPrompt:
    """Test system prompt assembly."""

    def test_base_only(self):
        prompt = build_system_prompt("You are an agent.")
        assert prompt == "You are an agent."

    def test_with_profile(self):
        profile = ProjectProfile(language="python", package_manager="pip")
        prompt = build_system_prompt("Base.", profile=profile)

        assert "Base." in prompt
        assert "Language: python" in prompt

    def test_with_instructions(self):
        prompt = build_system_prompt("Base.", project_instructions="# Custom instructions")

        assert "Base." in prompt
        assert "# Project Instructions" in prompt
        assert "# Custom instructions" in prompt

    def test_with_profile_and_instructions(self):
        profile = ProjectProfile(language="go", package_manager="go")
        prompt = build_system_prompt(
            "Base.",
            profile=profile,
            project_instructions="Use idiomatic Go.",
        )

        assert "Base." in prompt
        assert "Language: go" in prompt
        assert "Use idiomatic Go." in prompt

    def test_token_trimming_placeholder(self):
        # Token trimming is a simple char-based approximation for now.
        long_instructions = "x" * 10000
        prompt = build_system_prompt("Base.", project_instructions=long_instructions, max_tokens=100)

        # Should be trimmed to ~400 chars (100 tokens * 4).
        assert len(prompt) < 1000
        assert "truncated" in prompt


class TestContextIntegrationWithSession:
    """Test that session loads context automatically."""

    @pytest.mark.asyncio
    async def test_session_loads_instructions(self, temp_repo):
        # Write instructions.
        (Path(temp_repo) / "AGENTS.md").write_text("# Test instructions")

        provider = MockProvider(responses=[text_response("ok")])
        session = AgentSession(cwd=temp_repo, provider=provider, event_bus=EventBus())

        # System prompt should include instructions.
        assert "# Test instructions" in session.system

        await session.run("test")

        # Verify the system prompt was sent to provider.
        assert provider.calls[0].system is not None
        assert "# Test instructions" in provider.calls[0].system

    @pytest.mark.asyncio
    async def test_session_without_context_loading(self, temp_repo):
        (Path(temp_repo) / "AGENTS.md").write_text("# Should not be loaded")

        provider = MockProvider(responses=[text_response("ok")])
        session = AgentSession(
            cwd=temp_repo,
            provider=provider,
            event_bus=EventBus(),
            load_context=False,
        )

        # System prompt should NOT include instructions.
        assert "# Should not be loaded" not in session.system

    @pytest.mark.asyncio
    async def test_explicit_system_prompt_overrides(self, temp_repo):
        (Path(temp_repo) / "AGENTS.md").write_text("# Ignored")

        provider = MockProvider(responses=[text_response("ok")])
        session = AgentSession(
            cwd=temp_repo,
            provider=provider,
            event_bus=EventBus(),
            system="Custom system prompt",
        )

        # Explicit system prompt takes precedence.
        assert session.system == "Custom system prompt"
        assert "# Ignored" not in session.system
