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
from prompts import SYSTEM_PROMPT
from utils.helpers import extract_json
from backend.core.model_client import ModelClient
from backend.core.schemas import AgentAction
from backend.core.agent_ui import AgentUI
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
    history: List[Dict] = field(default_factory=list)   # conversation memory
    state: Dict[str, Any] = field(default_factory=dict)  # session store


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


async def _decide(model: ModelClient, messages: List[Dict]) -> Optional[Dict]:
    for attempt in range(config.RETRY_COUNT):
        try:
            raw = await model.generate(
                messages, stream=False,
                json_mode=(attempt == 0),
                schema=AGENT_SCHEMA if attempt == 0 else None,
            )
            decision = extract_json(raw)
            if decision:
                return decision
        except Exception as e:
            print(f"Decision error (attempt {attempt+1}): {e}")
    return None


# ── Main loop ────────────────────────────────────────────────────────────────

async def run_agent(query: str, ctx: AgentContext):
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(ctx.history[-20:])
    messages.append({"role": "user", "content": f"User Query: {query}"})

    for _ in range(config.MAX_STEPS):
        decision = await _decide(ctx.model, messages)
        if not decision:
            await ctx.ui.notice("Model geçerli bir karar üretemedi.", "error")
            return

        await ctx.ui.step(decision.get("thought"), decision.get("plan") or [])
        tool_calls = _sanitize_tool_calls(decision.get("tool_calls") or [])

        if tool_calls:
            obs = await _run_tools(tool_calls, ctx)
            messages.append({"role": "assistant", "content": json.dumps(decision, ensure_ascii=False)})
            messages.append({"role": "user", "content": f"OBSERVATION (Tool Results):\n{obs}"})
            continue

        # No tools → final answer.
        answer = (decision.get("final_answer") or "").strip()
        if answer:
            await _stream_text(ctx.ui, answer)
        else:
            answer = await _compose(ctx.model, messages, ctx.ui)
        await ctx.ui.final(answer)
        ctx.history.append({"role": "user", "content": query})
        ctx.history.append({"role": "assistant", "content": answer})
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

    # Argument shaping (mirrors the old tool_manager special-cases).
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


def _serialize_artifacts(items: List[Any]) -> List[Dict]:
    """Turn tool artifacts into JSON-serializable descriptors for the frontend."""
    out = []
    for item in items:
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
                    out.append({"type": "file", "path": item})
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
