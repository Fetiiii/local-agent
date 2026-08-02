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

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Form
from fastapi.responses import FileResponse

from backend.core.settings import settings
from backend.core.agent_ui import AgentUI
from backend.core.agent import AgentContext, run_agent
from backend.core.model_client import ModelClient
from backend.core.rag import get_rag_manager
from backend.ingestion.ingestor import UniversalIngestor
from backend.tools import ToolRegistry
from backend.tools.data_analyst import DataAnalystTool
from backend.tools.web_search import WebSearchTool
from backend.tools.web_scraper import WebScraperTool
from backend.tools.shell_executor import ShellExecutorTool
from backend.tools.image_analysis import ImageAnalysisTool
from backend.tools.file_editing.file_reader import FileReaderTool
from backend.tools.file_editing.file_architect import FileArchitectTool
from backend.tools.file_editing.file_surgeon import FileSurgeonTool

FRONTEND_DIR = Path(__file__).parent / "frontend"
UPLOAD_DIR = Path(__file__).parent / "data" / "temp" / "uploads"
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}

app = FastAPI(title="Local Agent")

# Live WebSocket sessions, so HTTP uploads can attach to the right conversation.
SESSIONS: dict[str, "AgentContext"] = {}
_ingestor = UniversalIngestor()


def build_registry() -> ToolRegistry:
    reg = ToolRegistry()
    for t in (DataAnalystTool(), WebSearchTool(), WebScraperTool(), ShellExecutorTool(),
              ImageAnalysisTool(model_name=settings.vision_model),
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
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/api/models")
async def list_models():
    provider = (settings.llm_provider or "ollama").lower()
    try:
        if provider == "openai":
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
                       rag=get_rag_manager())
    sid = uuid.uuid4().hex
    SESSIONS[sid] = ctx
    await ui._send({"type": "session", "id": sid})
    current: asyncio.Task | None = None

    async def _run(text: str):
        try:
            await run_agent(text, ctx)
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
                    ctx.model = ModelClient(model_name=msg["model"])
                current = asyncio.create_task(_run(msg.get("content", "")))
            elif mtype == "approval_response":
                ui.resolve_approval(msg.get("id"), bool(msg.get("approved")))
    except WebSocketDisconnect:
        if current and not current.done():
            current.cancel()
    finally:
        SESSIONS.pop(sid, None)
