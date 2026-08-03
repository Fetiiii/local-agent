"""
Headless agent core — Chainlit-free.

run_agent(query, ctx) drives the think → tool → observe → answer loop, emitting
events to ctx.ui (an AgentUI). No UI framework is imported here; the transport
(WebSocket, tests, …) supplies the adapter.
"""

from __future__ import annotations

import os
import json
import uuid
import asyncio
import base64
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import config
from backend.core.settings import settings
from prompts import SYSTEM_PROMPT
from utils.helpers import extract_json
from backend.core.model_client import ModelClient
from backend.core.schemas import AgentAction
from backend.core.agent_ui import AgentUI
from backend.core import memory as mem
from backend.tools import ToolRegistry

AGENT_SCHEMA = AgentAction.model_json_schema()
MAX_TOOL_CALLS = 8
MAX_OBS_CHARS = 8000

_COMPOSE_INSTRUCTION = (
    "Based on everything above, write your final answer to the user now. "
    "Reply in the user's language as clear prose (Markdown allowed). "
    "Do NOT output JSON and do NOT call tools."
)


@dataclass
class AgentContext:
    ui: AgentUI
    model: ModelClient
    registry: ToolRegistry
    rag: Any = None                                      # RAGManager (optional)
    thread_id: Optional[str] = None                      # persisted conversation id
    history: List[Dict] = field(default_factory=list)    # conversation memory
    state: Dict[str, Any] = field(default_factory=dict)  # session store
    max_steps: Optional[int] = None                      # agent-loop cap (UI override)


# ── Decision ─────────────────────────────────────────────────────────────────

def _sanitize_tool_calls(tool_calls: List[Dict]) -> List[Dict]:
    seen, clean = set(), []
    for tc in tool_calls:
        if not isinstance(tc, dict) or not tc.get("name"):
            continue
        key = (tc.get("name"), json.dumps(tc.get("args", {}), sort_keys=True, ensure_ascii=False))
        if key in seen:
            continue
        seen.add(key)
        clean.append(tc)
        if len(clean) >= MAX_TOOL_CALLS:
            break
    return clean


_ESCAPES = {'"': '"', '\\': '\\', '/': '/', 'b': '\b', 'f': '\f', 'n': '\n', 'r': '\r', 't': '\t'}


def _value_start(buf: str, key: str) -> int:
    """Index of a JSON key's value (after `"key":` + whitespace), or -1."""
    i = buf.find(key)
    if i < 0:
        return -1
    j = buf.find(":", i + len(key))
    if j < 0:
        return -1
    k = j + 1
    while k < len(buf) and buf[k] in " \t\r\n":
        k += 1
    return k


def _decode_json_string(buf: str, start: int):
    """Decode a JSON string starting at `start` (the opening quote).
    Returns (decoded_so_far, closed). Stops safely mid-escape when partial."""
    out: List[str] = []
    i, n = start + 1, len(buf)
    while i < n:
        c = buf[i]
        if c == "\\":
            if i + 1 >= n:
                return ("".join(out), False)  # incomplete escape → wait
            e = buf[i + 1]
            if e == "u":
                if i + 6 > n:
                    return ("".join(out), False)  # incomplete \uXXXX
                try:
                    out.append(chr(int(buf[i + 2:i + 6], 16)))
                except ValueError:
                    out.append(buf[i + 2:i + 6])
                i += 6
                continue
            out.append(_ESCAPES.get(e, e))
            i += 2
            continue
        if c == '"':
            return ("".join(out), True)  # closed
        out.append(c)
        i += 1
    return ("".join(out), False)  # ran out → partial


def _extract_string_field(buf: str, key: str):
    """(value_so_far, closed) for a string field, or (None, False) if not started."""
    k = _value_start(buf, key)
    if k < 0 or k >= len(buf) or buf[k] != '"':
        return (None, False)
    return _decode_json_string(buf, k)


def _extract_string_array(buf: str, key: str) -> Optional[List[str]]:
    """Fully-closed string items of an array field so far, or None if not started."""
    k = _value_start(buf, key)
    if k < 0 or k >= len(buf) or buf[k] != "[":
        return None
    items: List[str] = []
    i, n = k + 1, len(buf)
    while i < n:
        c = buf[i]
        if c in " \t\r\n,":
            i += 1
            continue
        if c == "]":
            break
        if c == '"':
            val, closed = _decode_json_string(buf, i)
            if not closed:
                break
            items.append(val)
            # advance past the closed string (walk to the unescaped closing quote)
            j = i + 1
            while j < n:
                if buf[j] == "\\":
                    j += 2
                    continue
                if buf[j] == '"':
                    j += 1
                    break
                j += 1
            i = j
        else:
            i += 1
    return items


class _DecisionStreamer:
    """Progressively surfaces thought / plan / final_answer from a streaming JSON
    decision so the user watches the model work live."""

    def __init__(self, ui: AgentUI):
        self.ui = ui
        self.buf = ""
        self._thought_sent = 0
        self._thought_done = False
        self._final_sent = 0
        self._final_done = False
        self._plan_sent: List[str] = []
        self.streamed_final = False

    async def feed(self, chunk: str):
        self.buf += chunk
        # thought
        if not self._thought_done:
            val, closed = _extract_string_field(self.buf, '"thought"')
            if val is not None:
                if len(val) > self._thought_sent:
                    await self.ui.thinking(val[self._thought_sent:])
                    self._thought_sent = len(val)
                if closed:
                    self._thought_done = True
                    await self.ui.thinking(done=True)
        # plan
        items = _extract_string_array(self.buf, '"plan"')
        if items is not None and len(items) > len(self._plan_sent):
            self._plan_sent = list(items)
            await self.ui.plan(list(items))
        # final_answer
        if not self._final_done:
            val, closed = _extract_string_field(self.buf, '"final_answer"')
            if val is not None:
                if len(val) > self._final_sent:
                    await self.ui.token(val[self._final_sent:])
                    self._final_sent = len(val)
                    self.streamed_final = True
                if closed:
                    self._final_done = True

    async def finish(self):
        if self._thought_sent and not self._thought_done:
            await self.ui.thinking(done=True)


async def _decide(model: ModelClient, messages: List[Dict], ui: AgentUI):
    """Return (decision, streamer). `streamer` is set only when attempt 0 streamed
    the decision live (so run_agent knows the answer was already surfaced)."""
    for attempt in range(config.RETRY_COUNT):
        try:
            if attempt == 0:
                gen = await model.generate(messages, stream=True, json_mode=True, schema=AGENT_SCHEMA)
                streamer = _DecisionStreamer(ui)
                raw = ""
                if isinstance(gen, str):
                    raw = gen
                    await streamer.feed(gen)
                else:
                    async for chunk in gen:
                        raw += chunk
                        await streamer.feed(chunk)
                await streamer.finish()
                decision = extract_json(raw)
                if decision:
                    return decision, streamer
                await ui.thinking(reset=True)  # drop partial live thought before retry
            else:
                raw = await model.generate(messages, stream=False, json_mode=False, schema=None)
                decision = extract_json(raw)
                if decision:
                    return decision, None
        except Exception as e:
            print(f"Decision error (attempt {attempt+1}): {e}")
            try:
                await ui.thinking(reset=True)
            except Exception:
                pass
    return None, None


# ── Main loop ────────────────────────────────────────────────────────────────

async def run_agent(query: str, ctx: AgentContext):
    system_content = mem.system_prompt_with_memory(SYSTEM_PROMPT, ctx.state.get("summary", ""))
    messages = [{"role": "system", "content": system_content}]
    messages.extend(ctx.history[-mem.MAX_RECENT:])

    # Retrieve relevant document/memory context (RAG) + any uploaded-file hint.
    context_str = ""
    if ctx.rag is not None:
        try:
            chunks = await asyncio.to_thread(ctx.rag.search, query, 3)
            context_str = "\n---\n".join(chunks)
        except Exception as e:
            print(f"RAG search error: {e}")
    user_content = f"User Query: {query}{ctx.state.get('file_hint', '')}"
    if context_str:
        user_content += f"\n\nContext from Files (RAG):\n{context_str}"
    messages.append({"role": "user", "content": user_content})

    for _ in range(ctx.max_steps or config.MAX_STEPS):
        decision, streamer = await _decide(ctx.model, messages, ctx.ui)
        if not decision:
            await ctx.ui.notice("Model geçerli bir karar üretemedi.", "error")
            return

        plan = decision.get("plan") or []
        if streamer is None:
            # Non-streamed fallback: surface thought + plan in one step event.
            await ctx.ui.step(decision.get("thought"), plan)
        elif plan:
            # Streamed path already surfaced thought/plan live; sync the exact plan.
            await ctx.ui.plan(plan)
        tool_calls = _sanitize_tool_calls(decision.get("tool_calls") or [])

        if tool_calls:
            obs = await _run_tools(tool_calls, ctx)
            messages.append({"role": "assistant", "content": json.dumps(decision, ensure_ascii=False)})
            messages.append({"role": "user", "content": f"OBSERVATION (Tool Results):\n{obs}"})
            continue

        # No tools → final answer.
        answer = (decision.get("final_answer") or "").strip()
        if answer:
            # If the streaming decision already emitted the answer live, don't re-stream.
            if not (streamer and streamer.streamed_final):
                await _stream_text(ctx.ui, answer)
        else:
            answer = await _compose(ctx.model, messages, ctx.ui)
        await ctx.ui.final(answer)
        ctx.history.append({"role": "user", "content": query})
        ctx.history.append({"role": "assistant", "content": answer})
        # Background (non-blocking) summarization once the buffer overflows.
        asyncio.create_task(mem.summarize_if_needed(ctx))
        return

    await ctx.ui.notice("Maksimum adım sayısına ulaşıldı.", "warn")


async def _stream_text(ui: AgentUI, text: str):
    chunk = max(24, len(text) // 150)
    for i in range(0, len(text), chunk):
        await ui.token(text[i:i + chunk])
        await asyncio.sleep(0.01)


async def _compose(model: ModelClient, messages: List[Dict], ui: AgentUI) -> str:
    full = ""
    try:
        gen = await model.generate(messages + [{"role": "user", "content": _COMPOSE_INSTRUCTION}],
                                   stream=True, json_mode=False)
        if isinstance(gen, str):
            full = gen
            await ui.token(gen)
        else:
            async for c in gen:
                full += c
                await ui.token(c)
    except Exception as e:
        print(f"Compose error: {e}")
    return full.strip() or "✅ Tamamlandı."


# ── Tool execution ───────────────────────────────────────────────────────────

async def _run_tools(tool_calls: List[Dict], ctx: AgentContext) -> str:
    async def one(tc):
        tid = uuid.uuid4().hex[:8]
        name = tc.get("name")
        args = tc.get("args", {}) or {}
        await ctx.ui.tool_start(tid, name, args)
        text, artifacts = await _exec_tool(name, args, ctx)
        capped = text if len(text) <= MAX_OBS_CHARS else text[:MAX_OBS_CHARS] + "\n… [truncated]"
        await ctx.ui.tool_end(tid, name, capped, artifacts)
        return f"### Tool '{name}' Result:\n{capped}"

    combined = await asyncio.gather(*[one(t) for t in tool_calls])
    return "\n\n---\n\n".join(combined)


async def _exec_tool(name: str, args: Dict, ctx: AgentContext):
    tool = ctx.registry.get(name)
    if not tool:
        return (f"❌ Tool '{name}' not found.", [])

    # Argument shaping for tools that need it.
    if name == "web_search":
        kw = {"query": args.get("query", "")}
    elif name == "data_analyst":
        kw = {"code": args.get("code", "")}
    elif name == "image_analysis":
        p = args.get("image_path") or args.get("path")
        if not p or not os.path.exists(p):
            last = ctx.state.get("last_image_path")
            p = last if last and os.path.exists(last) else p
        if not p or not os.path.exists(p):
            return (f"❌ Image not found: {p}", [])
        kw = {"image_path": p, "prompt": args.get("prompt", "Describe this image.")}
    else:
        kw = args

    # HITL approval for file-editing tools.
    if name in ("file_surgeon", "file_architect"):
        approved = await _approve_file_edit(name, kw, ctx.ui)
        if not approved:
            return ("❌ User rejected the change.", [])

    # HITL approval for host-mode shell commands (full-machine access).
    if name == "shell_executor" and settings.shell_host:
        detail = (f"**Host terminalinde çalıştırılacak:**\n```\n{kw.get('command', '')}\n```\n"
                  f"CWD: {kw.get('cwd') or '~'}")
        if not await ctx.ui.ask_approval("Terminal (host) komut onayı", detail):
            return ("❌ User rejected the command.", [])

    try:
        if asyncio.iscoroutinefunction(tool.run):
            res = await tool.run(**kw)
        else:
            res = await asyncio.to_thread(tool.run, **kw)
    except TypeError as e:
        return (f"❌ Invalid arguments for '{name}': {e}", [])
    except Exception as e:
        return (f"Tool error ({name}): {e}", [])

    if isinstance(res, dict):
        return (res.get("text", "") or "", _serialize_artifacts(res.get("artifacts", []) or []))
    return (str(res), [])


async def _approve_file_edit(name: str, kw: Dict, ui: AgentUI) -> bool:
    from backend.tools.file_editing.config import DATA_ROOT
    from backend.tools.file_editing.backup.backup_manager import BackupManager

    backup_mgr = BackupManager()
    if name == "file_architect":
        files = kw.get("files", {}) or {}
        if not files:
            return True
        preview = "**FileArchitect will create/modify:**\n" + "\n".join(
            f"- `{p}` ({len(c)} chars)" for p, c in files.items())
        if not await ui.ask_approval("Dosya oluşturma onayı", preview):
            return False
        paths = [DATA_ROOT / p for p in files if (DATA_ROOT / p).exists()]
        if paths:
            try:
                backup_mgr.create_backup(paths, action="FileArchitect batch write")
            except Exception:
                pass
        return True

    # file_surgeon
    rel = kw.get("path")
    target = DATA_ROOT / rel if rel else None
    if not target or not target.exists():
        return True  # let the tool report file-not-found itself
    detail = (f"**FileSurgeon → `{rel}`**\n\n**Find:**\n```\n{kw.get('search_block','')}\n```\n"
              f"**Replace:**\n```\n{kw.get('replace_block','')}\n```")
    if not await ui.ask_approval("Dosya düzenleme onayı", detail):
        return False
    try:
        backup_mgr.create_backup([target], action=f"FileSurgeon edit {rel}")
    except Exception:
        pass
    return True


# Rich file-preview support (additive; see docs/frontend-api.md).
_MAX_FILE_TEXT = 200_000       # chars inlined for text-like files
_MAX_FILE_B64 = 6_000_000      # bytes inlined as a base64 data URI (e.g. PDF)
_TEXT_EXTS = {".txt", ".json", ".log", ".py", ".js", ".ts", ".tsx", ".jsx",
              ".css", ".yaml", ".yml", ".toml", ".ini", ".sql", ".sh", ".xml"}


def _read_text_file(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read(_MAX_FILE_TEXT)
    except Exception:
        return ""


def _b64_data_uri(path: str, mime: str) -> Optional[str]:
    try:
        if os.path.getsize(path) > _MAX_FILE_B64:
            return None
        with open(path, "rb") as f:
            return f"data:{mime};base64," + base64.b64encode(f.read()).decode()
    except Exception:
        return None


def _table_from(path: str, excel: bool = False) -> Optional[str]:
    try:
        import pandas as pd
        df = pd.read_excel(path) if excel else pd.read_csv(path)
        return df.head(50).to_html(index=False)
    except Exception:
        return None


def _file_descriptor(path: str) -> Dict:
    """Classify a produced file and inline a previewable payload (additive)."""
    ext = os.path.splitext(path)[1].lower()
    d: Dict[str, Any] = {"type": "file", "path": path, "name": os.path.basename(path)}
    if ext in (".html", ".htm"):
        d["kind"] = "html"
        d["text"] = _read_text_file(path)
    elif ext in (".md", ".markdown"):
        d["kind"] = "markdown"
        d["text"] = _read_text_file(path)
    elif ext == ".csv":
        d["kind"] = "csv"
        d["text"] = _read_text_file(path)
        d["table_html"] = _table_from(path)
    elif ext in (".xlsx", ".xls"):
        d["kind"] = "excel"
        d["table_html"] = _table_from(path, excel=True)
    elif ext == ".pdf":
        d["kind"] = "pdf"
        data = _b64_data_uri(path, "application/pdf")
        if data:
            d["data"] = data
    elif ext in _TEXT_EXTS:
        d["kind"] = "text"
        d["text"] = _read_text_file(path)
    else:
        d["kind"] = "binary"
    return d


def _serialize_artifacts(items: List[Any]) -> List[Dict]:
    """Turn tool artifacts into JSON-serializable descriptors for the frontend."""
    out = []
    # web_search returns a flat list of {title, link, snippet} dicts → one links block.
    link_items = [i for i in items if isinstance(i, dict) and i.get("link")]
    if link_items:
        out.append({"type": "links", "items": link_items})
    for item in items:
        if isinstance(item, dict):
            continue  # link dicts handled above
        try:
            # Plotly figure
            if item.__class__.__name__ == "Figure" and hasattr(item, "to_json"):
                out.append({"type": "plotly", "json": item.to_json()})
                continue
            # pandas DataFrame
            if item.__class__.__name__ == "DataFrame":
                out.append({"type": "table", "html": item.head(50).to_html(index=False)})
                continue
            # file path
            if isinstance(item, str) and os.path.exists(item):
                ext = os.path.splitext(item)[1].lower()
                if ext in (".png", ".jpg", ".jpeg", ".gif", ".webp"):
                    with open(item, "rb") as f:
                        b64 = base64.b64encode(f.read()).decode()
                    mime = "image/png" if ext == ".png" else "image/jpeg"
                    out.append({"type": "image", "data": f"data:{mime};base64,{b64}"})
                else:
                    out.append(_file_descriptor(item))
                continue
            # list of link dicts (web_search)
            if isinstance(item, list) and item and isinstance(item[0], dict):
                out.append({"type": "links", "items": item})
                continue
            if isinstance(item, str):
                out.append({"type": "text", "text": item})
        except Exception:
            continue
    return out
