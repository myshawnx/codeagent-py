"""Context and project profile management."""

from .builder import build_system_prompt, load_project_instructions, render_profile_context
from .memory import append_memory, read_memory, render_memory_for_prompt, write_memory
from .profile import detect_profile

__all__ = [
    "build_system_prompt",
    "load_project_instructions",
    "render_profile_context",
    "append_memory",
    "read_memory",
    "render_memory_for_prompt",
    "write_memory",
    "detect_profile",
]
