# Lokal Agent

A fully local AI agent system powered by [Ollama](https://ollama.com) or [llama.cpp](https://github.com/ggml-org/llama.cpp), with a custom FastAPI + WebSocket UI. Run open-weight LLMs (8B–200B+) on your own hardware with a rich tool ecosystem, multi-tier memory, RAG, a Docker-isolated code sandbox, and vision — no cloud required.

## Features

### Agent & Reasoning
- **ReAct-style agent loop** — think → plan → call tools → observe → repeat
- **Parallel tool calling** — multiple independent tools run concurrently (deduped & capped)
- **Structured outputs** — a JSON schema constrains the model's output (with JSON-repair fallback), so even small models drive tools reliably

### Memory (3 Tiers)
| Tier | Mechanism | Scope |
|------|-----------|-------|
| Short-term | Session message buffer (last 10 msgs) | Current conversation |
| Mid-term | ChromaDB episodic store (conversation summaries) | Across sessions |
| Long-term | JSON user profile via ReflectionAgent | Permanent preferences & project facts |

### RAG (Retrieval-Augmented Generation)
- Automatic document ingestion on file upload
- Semantic search over uploaded docs + past conversation summaries
- Embeddings via `all-MiniLM-L6-v2` (runs fully offline)
- Persistent vector store with ChromaDB

### Supported File Formats
PDF · DOCX · XLSX · XLS · CSV  (legacy `.doc` — convert to `.docx` first)

### Tools
| Tool | Description |
|------|-------------|
| `data_analyst` | Execute Python in a persistent IPython-like environment |
| `file_reader_v2` | Safely read files and explore directory trees |
| `file_architect` | Atomically create multiple files / scaffold project structures |
| `file_surgeon` | Edit existing files with 3-tier matching (exact → whitespace-tolerant → fuzzy) |
| `shell_executor` | Run shell commands (pip, npm, git…) in a sandboxed working directory |
| `web_search` | Search the web for links and titles |
| `web_scraper` | Extract readable content from a URL |
| `image_analysis` | Analyze images with a local vision model |

### UI — "Copper & Patina" (React + Vite + TypeScript + Tailwind)
A modern three-column app (conversations · chat · artifacts) served by the same
FastAPI backend. Fully **offline** (all JS/CSS/fonts bundled locally, no CDN),
dark/light themes.
- **Live agent process** (Claude-Code style): a living plan/to-do checklist,
  collapsible reasoning, per-tool cards, and a **terminal view** for host shell
  commands — see the command and its output stream in real time
- **Streaming** Markdown answers with syntax-highlighted, copyable code blocks;
  a "thinking…" indicator until the first token (no dead-air)
- **Artifact side panel**: interactive Plotly charts, tables, images, web-search
  sources, and Claude-artifacts–style **HTML preview** (Code | Preview) plus
  Markdown/CSV/Excel/PDF previews
- Model selector, DeepSearch toggle, file upload → RAG, human-in-the-loop
  approval cards, sidebar conversation history with resume
- The legacy zero-build vanilla UI (`frontend/index.html`) is kept as a fallback
  and is served automatically if the React app hasn't been built yet

---

## Requirements

- **Python 3.11 or 3.12** (3.12 recommended; some ML deps like `torch`/`chromadb`
  may not yet have wheels for very new versions such as 3.14)
- A model backend, either:
  - [Ollama](https://ollama.com) running locally with at least one model pulled
    (e.g. `ollama pull llama3`), **or**
  - A llama.cpp `llama-server` (or any OpenAI-compatible endpoint) — see
    [Using llama.cpp](#using-llamacpp-instead-of-ollama)

---

## Quick Start

```bash
git clone https://github.com/Fetiiii/lokal-agent
cd lokal-agent
./setup.sh          # venv + deps + sandbox image + .env
# edit .env (MODEL_NAME, LLM_PROVIDER), then start your model backend, then:
./run.sh            # → http://localhost:8000
```

The manual steps are below if you prefer.

## Installation

```bash
git clone https://github.com/Fetiiii/lokal-agent
cd lokal-agent

python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

Or, using [uv](https://github.com/astral-sh/uv) (fast, handles the Python version too):

```bash
uv venv --python 3.12
uv pip install -r requirements.txt
```

---

## Configuration

Copy `.env.example` to `.env` and adjust:

```bash
cp .env.example .env
```

Key settings:

```env
# Provider: "ollama" (default) or "openai" (any OpenAI-compatible server,
# e.g. llama.cpp's llama-server, LM Studio, vLLM, or the real OpenAI API)
LLM_PROVIDER=ollama

# Default model to load on startup. Leave empty to auto-select the first
# locally available model.
MODEL_NAME=

# Only used when LLM_PROVIDER=openai (llama.cpp default shown):
OPENAI_BASE_URL=http://localhost:8080/v1
OPENAI_API_KEY=

# Model context window & default temperature
NUM_CTX=8192
TEMPERATURE=0.7

# Optional: vision model for image analysis
VISION_MODEL=qwen3-vl:2b

# Conversations are auto-persisted as JSON under data/conversations/ (no DB needed).

# Optional: Brave Search API key for the web_search tool
# https://brave.com/search/api/
WEB_SEARCH_API_KEY=

# Agent behaviour
RETRY_COUNT=3
MAX_STEPS=5
```

### Using llama.cpp instead of Ollama

Start `llama-server` with your GGUF model, then set:

```env
LLM_PROVIDER=openai
OPENAI_BASE_URL=http://localhost:8080/v1
MODEL_NAME=<the model name llama-server reports>
```

---

## Sandbox (isolated code execution)

`shell_executor` and `data_analyst` run model-generated code inside a
**hardened, per-session Docker container** instead of directly on your machine.
Each session gets its own container (non-root user, dropped Linux capabilities,
`no-new-privileges`, memory/CPU/PID limits, network off by default) with only
`data/exports/` mounted at `/workspace`. It's destroyed when the chat ends.

`data_analyst` keeps a **persistent Python kernel** inside that container, so
variables survive across calls while all execution stays isolated; plots and
DataFrames are streamed back to the sidebar over the shared volume.

Build the image once:

```bash
docker build -t localagent-sandbox:latest -f docker/sandbox.Dockerfile .
```

Configure via `.env`:

```env
SANDBOX_BACKEND=auto            # auto | docker | local
SANDBOX_ALLOW_NETWORK=false     # set true to allow pip/npm/git installs
```

- `auto` — use Docker when available, otherwise fall back to host execution.
- `docker` — require Docker; refuse to run on the host if it's missing.
- `local` — run on the host directly (no isolation).

Without Docker the agent still works (`auto` → host), so this is an opt-in
safety layer, not a hard dependency.

---

## Vision (image analysis)

`image_analysis` needs a **vision model**, which is separate from the main text
model. Two ways to provide one:

- **llama.cpp** — launch `llama-server` with a multimodal projector, so the same
  server serves both text and images:
  ```bash
  llama-server -m model.gguf --mmproj mmproj-F16.gguf -c 16384 -ngl 99 --jinja
  ```
  Leave `VISION_*` empty; it reuses `OPENAI_BASE_URL`. (VL model GGUFs ship the
  `mmproj-*.gguf` projector separately in their repo — download it too.)
- **Ollama** — set `VISION_PROVIDER=ollama` and pull a vision model:
  ```bash
  ollama pull qwen2.5vl:3b   # then set VISION_MODEL=qwen2.5vl:3b
  ```

If no vision backend is available, `image_analysis` returns a clear error
instead of failing silently.

---

## Running

Make sure your model backend is running (Ollama, or a llama.cpp `llama-server`
— see [Configuration](#configuration)).

**Build the frontend once** (produces `webui/dist/`, which FastAPI serves):

```bash
cd webui && npm install && npm run build && cd ..
```

Then start the web server:

```bash
.venv/bin/uvicorn server:app --host 127.0.0.1 --port 8000
```

Open [http://localhost:8000](http://localhost:8000) in your browser. If you skip
the build step, the server falls back to the legacy vanilla UI automatically.

**Frontend development** (hot-reload, proxies `/ws` + `/api` + `/static` to :8000):

```bash
cd webui && npm run dev    # http://localhost:5173
```

Conversations are persisted as JSON files under `data/conversations/` and appear
in the sidebar; click one to resume it.

---

## Project Structure

```
lokal-agent/
├── server.py                   # FastAPI + WebSocket entry point (serves webui/dist)
├── webui/                       # React + Vite + TS frontend ("Copper & Patina")
│   ├── src/                     # components (chat · agent · artifacts · layout)
│   └── dist/                    # build output served by FastAPI (npm run build)
├── frontend/index.html         # Legacy vanilla UI (fallback, no build step)
├── prompts.py                  # System prompts for the agent
├── config.py                   # Thin proxy over backend.core.settings
├── docker/sandbox.Dockerfile   # Image for the code-execution sandbox
│
├── backend/
│   ├── core/
│   │   ├── agent.py            # Headless agent loop (run_agent)
│   │   ├── agent_ui.py         # Transport-agnostic event interface
│   │   ├── memory.py           # 3-tier memory (summary + episodic + profile)
│   │   ├── conversations.py    # JSON conversation persistence
│   │   ├── model_client.py     # Provider facade (streaming + structured output)
│   │   ├── providers/          # Ollama + OpenAI-compatible backends
│   │   ├── rag.py              # ChromaDB RAG + episodic memory
│   │   ├── reflection_agent.py # Long-term user profile extractor
│   │   ├── schemas.py          # Pydantic schemas for agent actions
│   │   └── settings.py         # Pydantic Settings (.env loader)
│   │
│   ├── ingestion/              # docling/markitdown → Markdown (lazy-loaded)
│   │
│   └── tools/
│       ├── data_analyst.py     # Persistent Python kernel (sandboxed)
│       ├── web_search.py · web_scraper.py · image_analysis.py · shell_executor.py
│       ├── sandbox/            # Docker isolation (shell + data_analyst)
│       └── file_editing/       # file_reader, file_architect, file_surgeon (+ HITL, backup)
│
├── utils/helpers.py            # JSON extraction/repair, model listing
├── tests/                      # test_all, test_researcher, test_file_editing
│
└── data/
    ├── vector_store/           # ChromaDB persistent store
    ├── memory/                 # user_profile.json (long-term memory)
    ├── conversations/          # Saved chats (JSON, one per conversation)
    ├── exports/                # Working dir for file tools (mounted into sandbox)
    └── temp/                   # Upload cache & backups
```

---

## Model Recommendations

This project targets open-weight local models. Structured outputs + JSON-repair let even small models (tested down to 4B) drive the tools reliably; larger models mainly improve reasoning quality.

| Size | Recommendation |
|------|----------------|
| 20–30B | Best balance of speed and instruction-following |
| 70–80B | Highest quality; use Q4_K_M or Q5_K_M for best results |
| 80B Q3 | Works but JSON formatting reliability drops noticeably |

---

## Known Limitations

- Single-user setup; not designed for multi-user deployment
- Vector store is shared across all sessions (no per-user isolation)
- `MAX_STEPS=5` and `num_ctx=8192` may be tight for complex multi-file tasks

---

## License

MIT
