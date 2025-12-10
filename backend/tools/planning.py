"""Heuristic planning tool that expands a goal into actionable steps."""

from __future__ import annotations

from typing import Any, Dict, List

from backend.tools import BaseTool, register_tool


class PlanningTool:
    name = "planning"
    description = "Create/refine a plan using a deterministic heuristic (no LLM)."

    DEFAULT_STEPS = [
        "Clarify requirements and success criteria.",
        "Inventory available context, assets, and constraints.",
        "Draft a step-by-step approach.",
        "Execute iteratively with checkpoints.",
        "Review results and adjust.",
    ]

    def run(
        self,
        goal: str,
        steps: List[str] | None = None,
        max_steps: int = 8,
        include_risks: bool = True,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Build a lightweight plan.
        - Expands/normalizes provided steps.
        - Adds domain-tailored steps based on keywords.
        - Returns risks/checklist to keep the loop grounded.
        """
        normalized_goal = (goal or "").strip()
        if max_steps <= 0:
            max_steps = 1

        base_steps = steps or self.DEFAULT_STEPS
        domain_steps = self._domain_steps(normalized_goal)
        combined = base_steps + domain_steps

        # De-duplicate while preserving order
        seen = set()
        ordered: List[str] = []
        for s in combined:
            key = s.strip().lower()
            if key and key not in seen:
                seen.add(key)
                ordered.append(s.strip())

        plan = ordered[:max_steps] if ordered else self.DEFAULT_STEPS[:max_steps]

        checklist = self._build_checklist(normalized_goal, plan)
        risks = self._risks(normalized_goal) if include_risks else []
        trace = [
            f"Thought: goal='{normalized_goal or '[unspecified]'}'",
            f"Action: generated {len(plan)} steps (max={max_steps})",
            "Observation: deterministic heuristic used (no LLM).",
        ]

        return {
            "status": "ok",
            "goal": normalized_goal,
            "plan": plan,
            "checklist": checklist,
            "risks": risks,
            "trace": trace,
            "reflection": "Review steps against constraints and update as you learn.",
        }

    def _domain_steps(self, goal: str) -> List[str]:
        """Add domain-specific steps based on simple keyword detection."""
        g = goal.lower()
        steps: List[str] = []
        if any(k in g for k in ["bug", "fix", "regression", "error", "exception"]):
            steps.extend(
                [
                    "Reproduce the issue and capture inputs/logs.",
                    "Identify scope and recent changes.",
                    "Patch, add regression test, and re-verify.",
                ]
            )
        if any(k in g for k in ["feature", "implement", "add", "build"]):
            steps.extend(
                [
                    "Define acceptance criteria and edge cases.",
                    "Design the minimal change (data flow, API, UI).",
                    "Implement incrementally and validate.",
                ]
            )
        if any(k in g for k in ["refactor", "cleanup", "maintain"]):
            steps.extend(
                [
                    "Identify risky areas and dependencies.",
                    "Refactor in small commits with tests.",
                    "Run checks and compare behavior vs baseline.",
                ]
            )
        if any(k in g for k in ["data", "analysis", "metric", "report"]):
            steps.extend(
                [
                    "Pin data sources and filters.",
                    "Compute/validate metrics on a small sample.",
                    "Summarize findings with assumptions and next steps.",
                ]
            )
        return steps

    def _build_checklist(self, goal: str, plan: List[str]) -> List[str]:
        items = [
            "Confirm constraints (time, scope, approvals).",
            "List dependencies/owners and data sources.",
            "Define done/success criteria.",
        ]
        if any(k in goal.lower() for k in ["test", "qa", "verify", "regression"]):
            items.append("Enumerate test cases (happy path, edge, failure).")
        if len(plan) > 0:
            items.append("Add measurable checkpoints for each step.")
        return items

    def _risks(self, goal: str) -> List[str]:
        g = goal.lower()
        risks = [
            "Hidden constraints or unstated requirements.",
            "Insufficient context leading to rework.",
            "Timeline slip if checkpoints are unclear.",
        ]
        if any(k in g for k in ["prod", "production", "data loss", "outage"]):
            risks.append("Impact to production/data integrity; require rollback plan.")
        if any(k in g for k in ["security", "auth", "privacy"]):
            risks.append("Security/privacy implications need review.")
        return risks


register_tool(PlanningTool())
