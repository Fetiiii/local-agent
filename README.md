# Lokal Agent

A fully local AI agent system powered by [Ollama](https://ollama.com) and [Chainlit](https://chainlit.io). Run large language models (20B, 30B, 80B+) on your own hardware with a rich tool ecosystem, multi-tier memory, RAG, and an optional multi-agent mode — no cloud required.

## Features

### Agent & Reasoning
- **ReAct-style agent loop** — think → plan → call tools → observe → repeat
- **Parallel tool calling** — multiple tools execute concurrently in a single step
- **Multi-agent mode** — a Supervisor routes tasks to a CoderAgent or ResearcherAgent (toggle in UI)
- **JSON repair** — handles malformed JSON output from quantized models automatically

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

### UI
- Streaming responses with step-by-step thought visibility
- Chat settings panel: model selector, temperature slider, multi-agent toggle
- Sidebar conversation history with resume support
- Dynamically lists all locally available Ollama models at startup

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

# Optional: persist conversation history across restarts (SQLite example)
# CHAINLIT_DATABASE_URL=sqlite+aiosqlite:///./data/chainlit.db

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

First generate the auth secret required by Chainlit's login (once):

```bash
chainlit create-secret
# copy the printed CHAINLIT_AUTH_SECRET=... line into your .env
```

(Optional) Enable sidebar history & resuming past chats by creating the
persistence tables once, then setting `CHAINLIT_DATABASE_URL` in `.env`:

```bash
mkdir -p data/temp
sqlite3 data/temp/chainlit.db < backend/database/chainlit_schema.sql
```

Then start the app:

```bash
chainlit run app.py
```

Then open [http://localhost:8000](http://localhost:8000) in your browser.

---

## Project Structure

```
lokal-agent/
├── app.py                      # Chainlit entry point, session wiring
├── prompts.py                  # System prompts for all agent roles
├── config.py                   # Thin proxy over backend.core.settings
│
├── backend/
│   ├── core/
│   │   ├── model_client.py     # Async Ollama wrapper (streaming + JSON mode)
│   │   ├── rag.py              # ChromaDB RAG + episodic memory
│   │   ├── reflection_agent.py # Long-term user profile extractor
│   │   ├── schemas.py          # Pydantic schemas for agent actions
│   │   └── settings.py         # Pydantic Settings (.env loader)
│   │
│   ├── ingestion/
│   │   ├── ingestor.py         # Format router (PDF / DOCX / Excel)
│   │   └── parsers/            # PDF, DOCX, Excel parsers
│   │
│   ├── tools/
│   │   ├── data_analyst.py
│   │   ├── web_search.py
│   │   ├── web_scraper.py
│   │   ├── file_writer.py
│   │   ├── image_analysis.py
│   │   ├── project_scaffolder.py
│   │   ├── shell_executor.py
│   │   └── file_editing/       # file_reader, file_architect, file_surgeon
│   │
│   └── database/
│       └── db.py
│
├── utils/
│   ├── agent_engine.py         # Main agent loop + multi-agent supervisor
│   ├── memory_manager.py       # Short/mid-term memory + summarization
│   ├── tool_manager.py         # Tool dispatch
│   ├── ingestion_handler.py    # File upload handling
│   └── helpers.py              # JSON extraction/repair, Ollama model listing
│
├── tests/
│   ├── test_all.py
│   ├── test_memory.py
│   ├── test_researcher.py
│   └── test_file_editing.py
│
└── data/
    ├── vector_store/           # ChromaDB persistent store
    ├── memory/                 # user_profile.json (long-term memory)
    ├── exports/                # Working directory for file tools
    └── temp/                   # Upload cache & backups
```

---

## Model Recommendations

This project is designed for larger local models. Smaller models (7B) often struggle with the strict JSON output format required by the agent loop.

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
