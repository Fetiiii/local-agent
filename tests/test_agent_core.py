"""
Tests for the headless agent core (no LLM / Docker / network required).

Covers: _sanitize_tool_calls, _serialize_artifacts, the run_agent loop (with a
scripted fake model + fake tools), conversation persistence, and memory.
Run:  python tests/test_agent_core.py
"""

from __future__ import annotations

import asyncio
import json
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
    async def answer_reset(self): self.events.append(("answer_reset",))
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

    async def generate(self, messages, stream=False, json_mode=False, schema=None, max_tokens=None):
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


# ── extract_json: final_answer salvage ───────────────────────────────────────

def test_final_answer_salvage():
    print("\n── extract_json: final_answer salvage ──")
    from utils.helpers import extract_json

    # Unescaped inner quote lands before a `, "word":` pattern → json_repair alone
    # truncates. Salvage must recover the full prose. (Reproduces the DeepResearch
    # answer-cut-off bug.)
    raw = ('{"thought":"ok","tool_calls":[],"final_answer":"Model bir "olasilik '
           'motoru"dur; bir bilginin dogrulugunu", "kaynak": "tahmin eder ve '
           'aciklama uzun uzun devam ediyordu"}')
    d = extract_json(raw)
    fa = (d or {}).get("final_answer") or ""
    check("recovers full prose past the unescaped quote", "devam ediyordu" in fa)
    check("recovered answer far longer than the truncation point", len(fa) > 60)

    # Clean answer is left exactly as-is (salvage must not meddle).
    clean = '{"thought":"x","tool_calls":[],"final_answer":"Merhaba, nasil yardimci olabilirim?"}'
    d = extract_json(clean)
    check("clean answer unchanged", (d or {}).get("final_answer") == "Merhaba, nasil yardimci olabilirim?")

    # Tool-call mode: final_answer stays null, salvage must not fire.
    tool = '{"thought":"ara","tool_calls":[{"name":"web_search","args":{"q":"x"}}],"final_answer":null}'
    d = extract_json(tool)
    check("tool mode keeps final_answer null", (d or {}).get("final_answer") in (None, ""))
    check("tool mode keeps the tool call", len((d or {}).get("tool_calls") or []) == 1)


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


def test_answer_is_complete():
    print("\n── _answer_is_complete (heuristic) ──")
    from backend.core.agent import _answer_is_complete
    BIG, SMALL = 5000, 500
    long_ok = "Bu tam ve düzgün bir sentez cevabıdır. " * 40  # >800 ch, ends with '.'
    check("empty → incomplete", not _answer_is_complete("", BIG))
    check("big-obs long prose ending in '.' → complete", _answer_is_complete(long_ok, BIG))
    check("big-obs cut mid-sentence → incomplete", not _answer_is_complete("cevap ortada kesildi ve", BIG))
    check("big-obs ending in ':' → incomplete (enumeration cut)", not _answer_is_complete("İşte üç neden:", BIG))
    check("big-obs short stub (ends '.') → incomplete", not _answer_is_complete("Kısa cevap.", BIG))
    # Light-tool (small obs) answers are trusted as-is, even when terse/non-prose.
    check("small-obs terse 'Sonuç: 42' → complete", _answer_is_complete("Sonuç: 42", SMALL))
    check("small-obs value ending in digit → complete", _answer_is_complete("Ortalama = 42.5 → 3", SMALL))
    check("small-obs empty still incomplete", not _answer_is_complete("", SMALL))


async def test_run_agent_recompose_on_truncated_after_tools():
    print("\n── run_agent: truncated final after LARGE obs → answer_reset + compose ──")
    model = FakeModel([
        '{"tool_calls": [{"name": "deep_research", "args": {"query": "x"}}]}',
        # grammar final_answer cut mid-sentence (no terminal punctuation)
        '{"final_answer": "Bu cevap ortada kesiliyor ve düzgün bitmiyor bu yüzden"}',
        'Tam ve düzgün derlenmiş nihai cevap burada, noktayla biter.',   # _compose output
    ])
    ctx = _ctx(model, tools=[FakeTool("deep_research", "x" * 5000)])  # large synthesis obs
    await run_agent("q", ctx)
    kinds = ctx.ui.kinds()
    final = [e for e in ctx.ui.events if e[0] == "final"][-1][1]
    check("answer_reset emitted (truncated live answer cleared)", "answer_reset" in kinds)
    check("final is the composed answer", "Tam ve düzgün" in final)
    check("truncated grammar answer discarded", "ortada kesiliyor" not in final)


async def test_run_agent_complete_after_big_obs_no_recompose():
    print("\n── run_agent: complete prose after LARGE obs → used directly ──")
    long_complete = "Bu, deep_research bulgularının tam bir sentezidir. " * 30  # >800, ends '.'
    model = FakeModel([
        '{"tool_calls": [{"name": "deep_research", "args": {"query": "x"}}]}',
        json.dumps({"final_answer": long_complete}, ensure_ascii=False),
        # no 3rd entry — a wrongful recompose would change the answer
    ])
    ctx = _ctx(model, tools=[FakeTool("deep_research", "x" * 5000)])
    await run_agent("q", ctx)
    check("no answer_reset (prose answer was complete)", "answer_reset" not in ctx.ui.kinds())
    final = [e for e in ctx.ui.events if e[0] == "final"][-1][1]
    check("complete answer used directly", "tam bir sentezidir" in final)


async def test_run_agent_terse_answer_light_tool_no_recompose():
    print("\n── run_agent: terse non-prose answer after LIGHT tool → not recomposed ──")
    model = FakeModel([
        '{"tool_calls": [{"name": "data_analyst", "args": {"code": "print(6*7)"}}]}',
        '{"final_answer": "Sonuç: 42"}',   # terse, ends in a digit — legitimately complete
        # no 3rd entry — a wrongful recompose (advisor\'s regression) would rewrite this
    ])
    ctx = _ctx(model, tools=[FakeTool("data_analyst", "42")])  # small obs
    await run_agent("q", ctx)
    check("no answer_reset (light-tool terse answer trusted)", "answer_reset" not in ctx.ui.kinds())
    final = [e for e in ctx.ui.events if e[0] == "final"][-1][1]
    check("terse answer used verbatim", "Sonuç: 42" in final)


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
    test_final_answer_salvage()
    test_serialize()
    await test_run_agent_tool_then_final()
    await test_run_agent_direct_final()
    await test_run_agent_runaway_tools()
    test_answer_is_complete()
    await test_run_agent_recompose_on_truncated_after_tools()
    await test_run_agent_complete_after_big_obs_no_recompose()
    await test_run_agent_terse_answer_light_tool_no_recompose()
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
