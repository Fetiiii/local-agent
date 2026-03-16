"""
backend/tools/file_editing/hitl/approval_manager.py
-----------------------------------------------------
Human-in-the-Loop (HITL) approval gate.

Before any file is modified the agent calls ``ApprovalManager.request_approval()``.
The manager presents the diff and returns one of three outcomes:

  APPROVED — write the proposed content as-is.
  REJECTED — abort; the file is not touched.
  EDITED   — the human (or orchestrator) supplies an alternative content
              that is written instead of the agent's proposal.

Design note: In the current implementation the "human" decision comes from a
pluggable ``decision_fn`` that defaults to an interactive stdin prompt.
In production you would replace (or wrap) this with a Chainlit UI action,
a web hook, or any async approval channel without changing the public API.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from backend.tools.file_editing.logging_config import logger


# ── Decision outcome ──────────────────────────────────────────────────────────

class ApprovalStatus(enum.Enum):
    """Possible outcomes of a human review."""
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EDITED   = "EDITED"


@dataclass
class ApprovalResult:
    """
    The outcome of a single approval request.

    Attributes
    ----------
    status:          APPROVED / REJECTED / EDITED.
    edited_content:  Only set when status == EDITED.
                     Contains the human-supplied replacement content.
    reason:          Optional explanation from the reviewer.
    """
    status: ApprovalStatus
    edited_content: Optional[str] = field(default=None)
    reason: str = field(default="")


# ── Default interactive decision function ────────────────────────────────────

def _stdin_decision(file_path: Path, diff: str) -> ApprovalResult:
    """
    CLI-based approval prompt (default).

    Prints the diff and asks the user to type A / R / E.
    Replace this with any async UI integration for production use.
    """
    print("\n" + "=" * 60)
    print(f"  HITL Approval Required — {file_path.name}")
    print("=" * 60)
    if diff:
        print(diff)
    else:
        print("  (no diff — file will be created from scratch)")
    print("=" * 60)

    while True:
        choice = input(
            "  [A]pprove  /  [R]eject  /  [E]dit content → "
        ).strip().upper()

        if choice == "A":
            return ApprovalResult(status=ApprovalStatus.APPROVED, reason="user approved")

        if choice == "R":
            reason = input("  Reason for rejection (optional): ").strip()
            return ApprovalResult(status=ApprovalStatus.REJECTED, reason=reason)

        if choice == "E":
            print(
                "  Paste/type the replacement content below. "
                "End with a line containing only '---END---':"
            )
            lines = []
            while True:
                line = input()
                if line == "---END---":
                    break
                lines.append(line)
            return ApprovalResult(
                status=ApprovalStatus.EDITED,
                edited_content="\n".join(lines),
                reason="user edited content",
            )

        print("  Please enter A, R, or E.")


# ── ApprovalManager ───────────────────────────────────────────────────────────

class ApprovalManager:
    """
    Gate that presents a diff to a human reviewer before any write.

    Parameters
    ----------
    decision_fn:
        Callable ``(file_path: Path, diff: str) → ApprovalResult``.
        Defaults to the interactive stdin prompt.
        Override for testing or UI integration.
    auto_approve:
        Set True to automatically approve all requests (useful for batch
        processing or non-interactive CI environments).  Always logs a warning.
    """

    def __init__(
        self,
        decision_fn: Optional[Callable[[Path, str], ApprovalResult]] = None,
        auto_approve: bool = False,
    ) -> None:
        self._decision_fn = decision_fn or _stdin_decision
        self._auto_approve = auto_approve

        if auto_approve:
            logger.warning(
                "ApprovalManager initialised with auto_approve=True — "
                "all changes will be written without human review."
            )

    # ── Public API ─────────────────────────────────────────────────────────────

    def request_approval(
        self,
        file_path: Path | str,
        diff: str,
        proposed_content: Optional[str] = None,
    ) -> ApprovalResult:
        """
        Present *diff* for human review and return the decision.

        Parameters
        ----------
        file_path:        Path to the file being modified.
        diff:             Unified diff string (from diff_generator).
        proposed_content: Full proposed new content (only used in EDITED flow).

        Returns
        -------
        ApprovalResult with ``.status`` and optional ``.edited_content``.
        """
        file_path = Path(file_path)

        if self._auto_approve:
            logger.info("approval auto-approved: %s", file_path.name)
            return ApprovalResult(status=ApprovalStatus.APPROVED, reason="auto-approved")

        result = self._decision_fn(file_path, diff)
        logger.info(
            "approval %s: %s%s",
            result.status.value,
            file_path.name,
            f" ({result.reason})" if result.reason else "",
        )
        return result

    def batch_approve(
        self,
        requests: list[Dict[str, Any]],
    ) -> list[ApprovalResult]:
        """
        Process a list of approval requests sequentially.

        Each item in *requests* is a dict with keys:
          ``file_path``, ``diff``, and optionally ``proposed_content``.

        Returns a list of ApprovalResult in the same order.
        """
        return [
            self.request_approval(
                req["file_path"],
                req["diff"],
                req.get("proposed_content"),
            )
            for req in requests
        ]
