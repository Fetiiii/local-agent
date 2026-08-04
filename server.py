"""
FastAPI + WebSocket server — the custom-UI transport (replaces Chainlit).

Serves the frontend and streams agent events over a WebSocket. The agent core
(backend.core.agent) is Chainlit-free; this file is the only web/transport layer.

Run:  .venv/bin/uvicorn server:app --host 127.0.0.1 --port 8000
"""

from __future__ import annotations

import os
import json
import asyncio
import uuid
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Form, Body
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import config
from backend.core.settings import settings
from backend.core.llama_manager import llama_manager
from backend.core.agent_ui import AgentUI
from backend.core.agent import AgentContext, run_agent
from backend.core.model_client import ModelClient
from backend.core.rag import get_rag_manager
from backend.core import conversations as convs
from backend.ingestion.ingestor import UniversalIngestor
from backend.tools import ToolRegistry
from backend.tools.data_analyst import DataAnalystTool
from backend.tools.web_search import WebSearchTool
from backend.tools.web_scraper import WebScraperTool
from backend.tools.deep_research import DeepResearchTool
from backend.tools.shell_executor import ShellExecutorTool
from backend.tools.image_analysis import ImageAnalysisTool
from backend.tools.file_editing.file_reader import FileReaderTool
from backend.tools.file_editing.file_architect import FileArchitectTool
from backend.tools.file_editing.file_surgeon import FileSurgeonTool

FRONTEND_DIR = Path(__file__).parent / "frontend"
WEBUI_DIST = Path(__file__).parent / "webui" / "dist"   # built React SPA (npm run build)
UPLOAD_DIR = Path(__file__).parent / "data" / "temp" / "uploads"
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}

app = FastAPI(title="Local Agent")


def _ensure_plotly_js():
    """Write the plotly.js bundled with the installed plotly package (offline, version-matched)."""
    target = FRONTEND_DIR / "vendor" / "plotly.min.js"
    if target.exists():
        return
    try:
        import plotly.offline
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(plotly.offline.get_plotlyjs(), encoding="utf-8")
        print("📊 plotly.js frontend/vendor/ altına yazıldı.")
    except Exception as e:
        print(f"⚠️ plotly.js üretilemedi: {e}")


_ensure_plotly_js()
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")
# Built SPA assets (JS/CSS/fonts). Mounted only when a build exists.
if (WEBUI_DIST / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=str(WEBUI_DIST / "assets")), name="assets")

# Live WebSocket sessions, so HTTP uploads can attach to the right conversation.
SESSIONS: dict[str, "AgentContext"] = {}
_ingestor = UniversalIngestor()


def _clamp(v, lo, hi):
    try:
        return max(lo, min(hi, type(lo)(v)))
    except (TypeError, ValueError):
        return None


def _apply_settings(ctx: "AgentContext", s: dict) -> None:
    """Apply UI generation settings to the live model / agent context."""
    if s.get("temperature") is not None:
        t = _clamp(s["temperature"], 0.0, 2.0)
        if t is not None:
            ctx.model.temperature = t
    if "top_p" in s:
        tp = s["top_p"]
        ctx.model.top_p = None if tp in (None, "") else _clamp(tp, 0.0, 1.0)
    if "max_tokens" in s:
        mt = _clamp(s.get("max_tokens") or 0, 0, 32768)
        ctx.model.max_tokens = mt or 0
    if s.get("max_steps") is not None:
        ms = _clamp(s["max_steps"], 1, 20)
        if ms is not None:
            ctx.max_steps = ms


def build_registry() -> ToolRegistry:
    reg = ToolRegistry()
    for t in (DataAnalystTool(), WebSearchTool(), WebScraperTool(), DeepResearchTool(),
              ShellExecutorTool(), ImageAnalysisTool(model_name=settings.vision_model),
              FileReaderTool(), FileArchitectTool(), FileSurgeonTool()):
        reg.register(t)
    return reg


# ── WebSocket UI adapter ─────────────────────────────────────────────────────

class WebSocketUI(AgentUI):
    def __init__(self, ws: WebSocket):
        self.ws = ws
        self._lock = asyncio.Lock()
        self._pending: dict[str, asyncio.Future] = {}

    async def _send(self, obj: dict):
        async with self._lock:
            await self.ws.send_text(json.dumps(obj, ensure_ascii=False))

    async def step(self, thought, plan):
        await self._send({"type": "step", "thought": thought, "plan": plan})

    async def thinking(self, text="", done=False, reset=False):
        msg = {"type": "thinking"}
        if reset:
            msg["reset"] = True
        elif done:
            msg["done"] = True
        else:
            msg["text"] = text
        await self._send(msg)

    async def plan(self, plan):
        await self._send({"type": "plan", "plan": plan})

    async def tool_start(self, tool_id, name, args):
        await self._send({"type": "tool_start", "id": tool_id, "name": name, "args": args})

    async def tool_end(self, tool_id, name, result, artifacts=None):
        await self._send({"type": "tool_end", "id": tool_id, "name": name,
                          "result": result, "artifacts": artifacts or []})

    async def token(self, text):
        await self._send({"type": "token", "text": text})

    async def final(self, text):
        await self._send({"type": "final", "text": text})

    async def notice(self, text, level="info"):
        await self._send({"type": "notice", "text": text, "level": level})

    async def ask_approval(self, title, detail) -> bool:
        rid = uuid.uuid4().hex[:8]
        fut: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending[rid] = fut
        await self._send({"type": "approval_request", "id": rid, "title": title, "detail": detail})
        try:
            return await fut
        finally:
            self._pending.pop(rid, None)

    def resolve_approval(self, rid: str, approved: bool):
        fut = self._pending.get(rid)
        if fut and not fut.done():
            fut.set_result(approved)


# ── HTTP endpoints ───────────────────────────────────────────────────────────

@app.get("/")
async def index():
    # Prefer the built React SPA; fall back to the legacy vanilla UI if unbuilt.
    spa = WEBUI_DIST / "index.html"
    return FileResponse(spa if spa.exists() else FRONTEND_DIR / "index.html")


@app.get("/api/models")
async def list_models():
    provider = (settings.llm_provider or "ollama").lower()
    try:
        if provider == "openai":
            # Local .gguf folder → real switchable list. Fall back to whatever the
            # running server reports (single loaded model) if no folder is set.
            local = llama_manager.list_models()
            if local:
                return {"provider": provider, "models": local,
                        "current": llama_manager.current(),
                        "manageable": settings.manage_llama_server}
            from openai import AsyncOpenAI
            client = AsyncOpenAI(base_url=settings.openai_base_url,
                                 api_key=settings.openai_api_key or "not-needed")
            resp = await client.models.list()
            return {"provider": provider, "models": [m.id for m in resp.data]}
        else:
            from utils.helpers import get_ollama_models
            return {"provider": provider, "models": await get_ollama_models()}
    except Exception as e:
        return {"provider": provider, "models": [], "error": str(e)}


@app.post("/api/model/switch")
async def switch_model(payload: dict = Body(...)):
    """Relaunch llama-server with a different local .gguf (UI model switch).
    Kills the current model, so any in-flight generation on it will error out."""
    res = await llama_manager.switch((payload or {}).get("model", ""))
    return res


@app.on_event("startup")
async def _startup():
    if (settings.llm_provider or "").lower() == "openai":
        await llama_manager.ensure_started()


@app.on_event("shutdown")
async def _shutdown():
    llama_manager.shutdown()


@app.get("/api/settings")
async def get_settings():
    """Current generation defaults, so the UI settings panel shows real values."""
    return {
        "temperature": settings.temperature,
        "top_p": 1.0,
        "max_tokens": 0,          # 0 = unlimited
        "max_steps": config.MAX_STEPS,
    }


@app.get("/api/conversations")
async def list_conversations():
    return await asyncio.to_thread(convs.list_all)


@app.delete("/api/conversations/{tid}")
async def delete_conversation(tid: str):
    ok = await asyncio.to_thread(convs.delete, tid)
    return {"ok": ok}


@app.post("/api/upload")
async def upload(session_id: str = Form(...), file: UploadFile = File(...)):
    ctx = SESSIONS.get(session_id)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    dest = UPLOAD_DIR / os.path.basename(file.filename)
    dest.write_bytes(await file.read())
    ext = dest.suffix.lower()

    if ext in IMAGE_EXTS:
        if ctx is not None:
            ctx.state["last_image_path"] = str(dest)
            ctx.state["file_hint"] = (
                f"\n[SYSTEM HINT]: An image was uploaded at '{dest}'. "
                "Use 'image_analysis' to inspect it.")
        return {"ok": True, "type": "image", "name": dest.name}

    # Document → ingest to Markdown → index in RAG.
    try:
        md = await asyncio.to_thread(_ingestor.ingest_file, str(dest))
        if not md:
            return {"ok": False, "name": dest.name, "error": "Desteklenmeyen/okunamayan dosya."}
        chunks = await asyncio.to_thread(get_rag_manager().add_document, md, dest.name)
        if ctx is not None:
            ctx.state["file_hint"] = (
                f"\n[SYSTEM HINT]: Uploaded file '{dest.name}' is indexed and searchable.")
        return {"ok": True, "type": "doc", "name": dest.name, "chunks": chunks}
    except Exception as e:
        return {"ok": False, "name": dest.name, "error": str(e)}


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    ui = WebSocketUI(ws)
    ctx = AgentContext(ui=ui, model=ModelClient(), registry=build_registry(),
                       rag=get_rag_manager(), thread_id=convs.new_id())
    sid = uuid.uuid4().hex
    SESSIONS[sid] = ctx
    await ui._send({"type": "session", "id": sid, "thread_id": ctx.thread_id})
    current: asyncio.Task | None = None

    async def _run(text: str):
        try:
            await run_agent(text, ctx)
            await asyncio.to_thread(convs.save, ctx.thread_id, ctx.history,
                                    ctx.state.get("summary", ""))
        except Exception as e:
            await ui.notice(f"Agent error: {e}", "error")
        finally:
            await ui._send({"type": "done"})

    try:
        while True:
            msg = json.loads(await ws.receive_text())
            mtype = msg.get("type")
            if mtype == "user_message":
                if msg.get("model") and msg["model"] != ctx.model.model_name:
                    # Preserve the user's generation settings across a model switch.
                    ctx.model = ModelClient(model_name=msg["model"],
                                            temperature=ctx.model.temperature,
                                            top_p=ctx.model.top_p,
                                            max_tokens=ctx.model.max_tokens)
                content = msg.get("content", "")
                if msg.get("deep_research"):
                    content = ("[DeepSearch modu] Bu soruyu 'deep_research' tool'unu "
                               "kullanarak derinlemesine araştır:\n" + content)
                # Orchestration mode (opt-in): manager may delegate to sub-agents this turn.
                ctx.orchestrate = bool(msg.get("orchestrate"))
                current = asyncio.create_task(_run(content))
            elif mtype == "approval_response":
                ui.resolve_approval(msg.get("id"), bool(msg.get("approved")))
            elif mtype == "settings":
                _apply_settings(ctx, msg.get("settings") or {})
            elif mtype == "persist":
                # Frontend's rich UI state (timeline + artifacts) for the current thread.
                await asyncio.to_thread(convs.save_ui, ctx.thread_id, msg.get("ui") or {})
            elif mtype == "resume":
                data = await asyncio.to_thread(convs.load, msg.get("id"))
                if data:
                    ctx.history = data.get("messages", [])
                    ctx.state["summary"] = data.get("summary", "")
                    ctx.thread_id = data["id"]
                    await ui._send({"type": "history", "thread_id": ctx.thread_id,
                                    "messages": ctx.history, "ui": data.get("ui")})
            elif mtype == "new":
                ctx.history = []
                ctx.state = {}
                ctx.thread_id = convs.new_id()
                await ui._send({"type": "thread", "id": ctx.thread_id})
    except WebSocketDisconnect:
        if current and not current.done():
            current.cancel()
    finally:
        SESSIONS.pop(sid, None)
