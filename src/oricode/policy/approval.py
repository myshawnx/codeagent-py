"""Approval handlers for policy confirmation decisions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class ApprovalRequest:
    """A request to approve a confirm-level tool call."""

    tool_name: str
    tool_input: dict
    reason: str


@dataclass(frozen=True)
class ApprovalDecision:
    """The result of an approval request."""

    approved: bool
    reason: str | None = None


class ApprovalHandler(Protocol):
    """Handles confirm-level policy verdicts outside the policy engine."""

    def approve(self, request: ApprovalRequest) -> ApprovalDecision:
        """Return whether the requested tool call may proceed."""
        ...


class AutoApprovalHandler:
    """Approves every confirmation request."""

    def approve(self, request: ApprovalRequest) -> ApprovalDecision:
        return ApprovalDecision(approved=True, reason="auto-approved")


class DenyApprovalHandler:
    """Denies every confirmation request without blocking for input."""

    def approve(self, request: ApprovalRequest) -> ApprovalDecision:
        return ApprovalDecision(approved=False, reason="non-interactive approval denied")


class RichPromptApprovalHandler:
    """Prompts the local CLI user for confirmation with Rich."""

    def approve(self, request: ApprovalRequest) -> ApprovalDecision:
        from rich.prompt import Confirm

        approved = Confirm.ask(
            f"Allow {request.tool_name} with input {request.tool_input}? "
            f"[dim]{request.reason}[/dim]",
            default=False,
        )
        return ApprovalDecision(
            approved=approved,
            reason="user approved" if approved else "user denied",
        )


@dataclass
class RecordingApprovalHandler:
    """Test/eval handler that records requests and returns scripted decisions."""

    decisions: list[ApprovalDecision] = field(default_factory=list)
    requests: list[ApprovalRequest] = field(default_factory=list)

    def approve(self, request: ApprovalRequest) -> ApprovalDecision:
        self.requests.append(request)
        if self.decisions:
            return self.decisions.pop(0)
        return ApprovalDecision(approved=False, reason="no scripted approval")
