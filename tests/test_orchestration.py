"""
Orchestration ("smart B") tests — no LLM / network. A scripted fake model drives
a manager that delegates to a coder sub-agent; we assert the sub-agent runs with
a SCOPED registry + focused prompt, its final is captured and fed back to the
manager, and the delegation is gated by ctx.orchestrate.

Run:  python tests/test_orchestration.py
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import os
os.environ.setdefault("SANDBOX_BACKEND", "local")
os.environ.setdefault("SHELL_HOST", "false")

from backend.core.agent import run_agent, AgentContext, _delegate, SUB_AGENTS
from backend.core.agent_ui import AgentUI
from backend.tools import ToolRegistry

PASS = "✅"
FAIL = "❌"
_fails = 0


def check(cond, label):
    global _fails
    print(f"  {PASS if cond else FAIL}  {label}")
    if not cond:
        _fails += 1


class CaptureUI(AgentUI):
    def __init__(self):
        self.steps, self.notices, self.tools = [], [], []
        self.final_text = None
    async def step(self, thought, plan): self.steps.append(thought)
    async def tool_start(self, tool_id, name, args): self.tools.append((name, args))
    async def tool_end(self, tool_id, name, result, artifacts=None): pass
    async def token(self, text): pass
    async def final(self, text): self.final_text = text
    async def notice(self, text, level="info"): self.notices.append(text)
    async def ask_approval(self, title, detail): return True


class FakeModel:
    """Returns scripted JSON decisions. Branches on whether the system prompt is
    the coder sub-agent's or the manager's; counts manager steps."""
    def __init__(self):
        self.mgr_calls = 0
        self.saw_coder_prompt = False
        self.coder_tools_seen = []

    async def generate(self, messages, stream=False, json_mode=False, schema=None):
        sysc = messages[0]["content"]
        if "CODER sub-agent" in sysc:
            self.saw_coder_prompt = True
            # Coder: one quick tool call, then finish (keeps within scope).
            # Detect whether we've already "run" a tool this sub-run.
            has_obs = any("OBSERVATION" in m.get("content", "") for m in messages)
            if not has_obs:
                return json.dumps({"thought": "read the tree",
                                   "tool_calls": [{"name": "file_reader_v2",
                                                   "args": {"action": "list_tree", "path": "."}}],
                                   "final_answer": None})
            return json.dumps({"thought": "verified",
                               "tool_calls": [],
                               "final_answer": "CODER: listed tree and verified."})
        # Manager
        self.mgr_calls += 1
        if self.mgr_calls == 1:
            return json.dumps({"thought": "delegate to coder",
                               "tool_calls": [{"name": "delegate",
                                               "args": {"agent": "coder", "task": "list the project tree"}}],
                               "final_answer": None})
        return json.dumps({"thought": "synthesize",
                           "tool_calls": [],
                           "final_answer": "MANAGER: coder finished the job."})


class FakeTool:
    def __init__(self, name, model_ref=None):
        self.name = name
        self.description = name
        self._m = model_ref
    def run(self, **kwargs):
        if self._m is not None:
            self._m.coder_tools_seen.append(self.name)
        return {"text": f"{self.name} ran with {kwargs}", "artifacts": []}


def full_registry(model):
    reg = ToolRegistry()
    for n in ["data_analyst", "file_reader_v2", "file_architect", "file_surgeon",
              "shell_executor", "web_search", "web_scraper", "deep_research", "image_analysis"]:
        reg.register(FakeTool(n, model_ref=model))
    return reg


async def test_delegation_happy_path():
    print("\n── delegation: manager → coder → back ──")
    ui = CaptureUI()
    model = FakeModel()
    ctx = AgentContext(ui=ui, model=model, registry=full_registry(model),
                       rag=None, thread_id="t", history=[], state={}, orchestrate=True)
    await run_agent("build something", ctx)

    check(model.saw_coder_prompt, "coder sub-agent ran with its focused prompt")
    check(("delegate", {"agent": "coder", "task": "list the project tree"}) in ui.tools,
          "manager emitted a 'delegate' tool_start")
    check(any("delege edildi" in n for n in ui.notices), "delegation start notice shown")
    check(any("tamamladı" in n for n in ui.notices), "delegation done notice shown")
    check(model.coder_tools_seen == ["file_reader_v2"],
          f"coder used only its scoped tool (saw: {model.coder_tools_seen})")
    check(ui.final_text == "MANAGER: coder finished the job.",
          f"manager produced the final after synthesizing (got: {ui.final_text!r})")


async def test_scope_enforced():
    print("\n── scope: researcher cannot see coder tools ──")
    from backend.core.agent import _scoped_registry
    model = FakeModel()
    reg = full_registry(model)
    sub = _scoped_registry(reg, SUB_AGENTS["researcher"]["tools"])
    check(sub.get("web_search") is not None, "researcher HAS web_search")
    check(sub.get("shell_executor") is None, "researcher does NOT have shell_executor")


async def test_gating():
    print("\n── gating: delegate refused when orchestrate is off ──")
    ui = CaptureUI()
    model = FakeModel()
    ctx = AgentContext(ui=ui, model=model, registry=full_registry(model),
                       rag=None, thread_id="t", history=[], state={}, orchestrate=False)
    text, arts = await _delegate({"agent": "coder", "task": "x"}, ctx)
    check("not enabled" in text, "delegation blocked when orchestrate=False")


async def test_bad_args():
    print("\n── validation: unknown agent / empty task ──")
    ui = CaptureUI()
    model = FakeModel()
    ctx = AgentContext(ui=ui, model=model, registry=full_registry(model),
                       rag=None, thread_id="t", history=[], state={}, orchestrate=True)
    t1, _ = await _delegate({"agent": "wizard", "task": "x"}, ctx)
    t2, _ = await _delegate({"agent": "coder", "task": "  "}, ctx)
    check("Unknown sub-agent" in t1, "unknown agent rejected")
    check("non-empty 'task'" in t2, "empty task rejected")


async def main():
    print("=" * 60)
    print("  ORCHESTRATION TESTS")
    print("=" * 60)
    await test_delegation_happy_path()
    await test_scope_enforced()
    await test_gating()
    await test_bad_args()
    print("\n" + "=" * 60)
    print(f"  {'ALL PASSED' if _fails == 0 else str(_fails) + ' FAILED'}")
    print("=" * 60)
    sys.exit(1 if _fails else 0)


if __name__ == "__main__":
    asyncio.run(main())
