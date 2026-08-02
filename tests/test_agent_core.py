"""
Tests for the headless agent core (no LLM / Docker / network required).

Covers: _sanitize_tool_calls, _serialize_artifacts, the run_agent loop (with a
scripted fake model + fake tools), conversation persistence, and memory.
Run:  python tests/test_agent_core.py
"""

from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import os
os.environ.setdefault("SANDBOX_BACKEND", "local")
os.environ.setdefault("SHELL_HOST", "false")

from backend.core.agent import (
    AgentContext, run_agent, _sanitize_tool_calls, _serialize_artifacts,
)
from backend.core.agent_ui import AgentUI
from backend.core import memory as mem
from backend.core import conversations as convs

_results: list[tuple[str, bool]] = []


def check(name: str, cond: bool, detail: str = ""):
    _results.append((name, bool(cond)))
    print(f"{'✅' if cond else '❌'}  {name}" + (f"  ({detail})" if detail and not cond else ""))


# ── Fakes ────────────────────────────────────────────────────────────────────

class CaptureUI(AgentUI):
    def __init__(self):
        self.events = []

    async def step(self, thought, plan): self.events.append(("step", thought, plan))
    async def tool_start(self, tid, name, args): self.events.append(("tool_start", name, args))
    async def tool_end(self, tid, name, result, artifacts=None): self.events.append(("tool_end", name, result, artifacts))
    async def token(self, text): self.events.append(("token", text))
    async def final(self, text): self.events.append(("final", text))
    async def notice(self, text, level="info"): self.events.append(("notice", text, level))
    async def ask_approval(self, title, detail): self.events.append(("approval", title)); return True

    def kinds(self):
        return [e[0] for e in self.events]


class FakeModel:
    def __init__(self, scripted):
        self.scripted = list(scripted)
        self.model_name = "fake"

    async def generate(self, messages, stream=False, json_mode=False, schema=None):
        resp = self.scripted.pop(0) if self.scripted else '{"final_answer": "done"}'
        if stream:
            async def _gen():
                yield resp
            return _gen()
        return resp


class FakeTool:
    def __init__(self, name, result="tool output"):
        self.name = name
        self._result = result

    def run(self, **kwargs):
        return {"text": self._result, "artifacts": []}


class FakeRegistry:
    def __init__(self, tools):
        self._tools = {t.name: t for t in tools}

    def get(self, name):
        return self._tools.get(name)


def _ctx(model, tools=(), rag=None):
    return AgentContext(ui=CaptureUI(), model=model, registry=FakeRegistry(list(tools)), rag=rag)


# ── _sanitize_tool_calls ─────────────────────────────────────────────────────

def test_sanitize():
    print("\n── _sanitize_tool_calls ──")
    dupes = [{"name": "t", "args": {"a": 1}}] * 20
    out = _sanitize_tool_calls(dupes)
    check("dedupes identical calls to 1", len(out) == 1)

    many = [{"name": "t", "args": {"i": i}} for i in range(20)]
    out = _sanitize_tool_calls(many)
    check("caps at MAX_TOOL_CALLS (8)", len(out) == 8)

    junk = [{"args": {}}, {"name": ""}, "nope", {"name": "ok", "args": {}}]
    out = _sanitize_tool_calls(junk)
    check("drops malformed calls", len(out) == 1 and out[0]["name"] == "ok")


# ── _serialize_artifacts ─────────────────────────────────────────────────────

def test_serialize():
    print("\n── _serialize_artifacts ──")
    links = [{"title": "A", "link": "http://a", "snippet": "s"},
             {"title": "B", "link": "http://b", "snippet": "s"}]
    out = _serialize_artifacts(links)
    check("web_search dicts → one links artifact", len(out) == 1 and out[0]["type"] == "links"
          and len(out[0]["items"]) == 2)

    out = _serialize_artifacts(["just text"])
    check("bare string → text artifact", out and out[0]["type"] == "text")

    out = _serialize_artifacts([])
    check("empty → no artifacts", out == [])


# ── run_agent loop ───────────────────────────────────────────────────────────

async def test_run_agent_tool_then_final():
    print("\n── run_agent: tool → final ──")
    model = FakeModel([
        '{"thought": "use tool", "tool_calls": [{"name": "echo", "args": {"x": 1}}]}',
        '{"thought": "done now", "final_answer": "The answer is 5."}',
    ])
    ctx = _ctx(model, tools=[FakeTool("echo", "echoed")])
    await run_agent("hello", ctx)
    kinds = ctx.ui.kinds()
    check("emitted a tool_start", "tool_start" in kinds)
    check("emitted a tool_end", "tool_end" in kinds)
    check("emitted final", "final" in kinds)
    final = [e for e in ctx.ui.events if e[0] == "final"][-1][1]
    check("final answer streamed directly", "answer is 5" in final)
    check("history has user+assistant", len(ctx.history) == 2 and ctx.history[0]["role"] == "user")


async def test_run_agent_direct_final():
    print("\n── run_agent: direct final (no tools) ──")
    model = FakeModel(['{"thought": "easy", "final_answer": "42"}'])
    ctx = _ctx(model)
    await run_agent("q", ctx)
    check("no tool calls", "tool_start" not in ctx.ui.kinds())
    check("final is 42", [e for e in ctx.ui.events if e[0] == "final"][-1][1] == "42")


async def test_run_agent_runaway_tools():
    print("\n── run_agent: runaway tool_calls are sanitized ──")
    dupes = ",".join(['{"name": "echo", "args": {}}'] * 30)
    model = FakeModel([
        f'{{"tool_calls": [{dupes}]}}',
        '{"final_answer": "done"}',
    ])
    ctx = _ctx(model, tools=[FakeTool("echo")])
    await run_agent("q", ctx)
    tool_starts = [e for e in ctx.ui.events if e[0] == "tool_start"]
    check("30 duplicate calls deduped to 1 execution", len(tool_starts) == 1)


# ── conversations ────────────────────────────────────────────────────────────

def test_conversations():
    print("\n── conversations ──")
    with tempfile.TemporaryDirectory() as tmp:
        convs.CONV_DIR = Path(tmp)
        tid = convs.new_id()
        history = [{"role": "user", "content": "Merhaba dünya bu bir test"},
                   {"role": "assistant", "content": "cevap"}]
        convs.save(tid, history, summary="özet")
        loaded = convs.load(tid)
        check("save/load round-trip", loaded and loaded["messages"] == history)
        check("title derived from first user msg", loaded["title"].startswith("Merhaba"))
        check("summary persisted", loaded["summary"] == "özet")
        listing = convs.list_all()
        check("list_all returns the conversation", any(c["id"] == tid for c in listing))
        convs.delete(tid)
        check("delete removes it", convs.load(tid) is None)


# ── memory ───────────────────────────────────────────────────────────────────

class FakeRag:
    def __init__(self): self.episodic = []
    def add_episodic_memory(self, text, ts): self.episodic.append(text)


def test_memory_prompt():
    print("\n── memory: prompt injection ──")
    sp = mem.system_prompt_with_memory("BASE", "")
    check("no summary → starts with BASE", sp.strip().startswith("BASE"))
    sp = mem.system_prompt_with_memory("BASE", "geçmiş özet")
    check("summary injected", "geçmiş özet" in sp)


async def test_memory_summarize():
    print("\n── memory: background summarization ──")
    # history longer than SUMMARIZE_THRESHOLD
    history = [{"role": "user" if i % 2 == 0 else "assistant", "content": f"msg{i}"}
               for i in range(20)]
    model = FakeModel([
        "ROLLING SUMMARY",                      # summary call
        '{"user_preferences": [], "project_facts": [], "correction_rules": []}',  # reflection
    ])
    rag = FakeRag()
    ctx = AgentContext(ui=CaptureUI(), model=model, registry=None, rag=rag, history=history)
    await mem.summarize_if_needed(ctx)
    check("history trimmed to MAX_RECENT", len(ctx.history) == mem.MAX_RECENT)
    check("summary set", ctx.state.get("summary") == "ROLLING SUMMARY")
    check("episodic memory recorded", len(rag.episodic) == 1)


# ── runner ───────────────────────────────────────────────────────────────────

async def main():
    print("=" * 60 + "\n  Agent Core — Test Suite\n" + "=" * 60)
    test_sanitize()
    test_serialize()
    await test_run_agent_tool_then_final()
    await test_run_agent_direct_final()
    await test_run_agent_runaway_tools()
    test_conversations()
    test_memory_prompt()
    await test_memory_summarize()

    total = len(_results)
    passed = sum(1 for _, ok in _results if ok)
    print("\n" + "=" * 60)
    print(f"  {passed}/{total} passed" + ("" if passed == total else "  ← FAILURES"))
    print("=" * 60)
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    asyncio.run(main())
