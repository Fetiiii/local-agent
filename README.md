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
PDF · DOCX · DOC · XLSX · XLS · CSV

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

- Python 3.11+
- [Ollama](https://ollama.com) running locally
- At least one LLM pulled in Ollama (e.g. `ollama pull llama3`)

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

---

## Configuration

Create a `.env` file in the project root:

```env
# Required: default model to load on startup
MODEL_NAME=llama3:latest

# Optional: vision model for image analysis
VISION_MODEL=qwen3-vl:2b

# Optional: persist conversation history across restarts
# Chainlit supports PostgreSQL and SQLite
# SQLite example:
CHAINLIT_DATABASE_URL=sqlite+aiosqlite:///./data/chainlit.db

# Optional: web search API key (e.g. Serper, Tavily)
WEB_SEARCH_API_KEY=

# Agent behaviour
RETRY_COUNT=3
MAX_STEPS=5
```

---

## Running

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
- Shell executor sandbox is path-based, not containerized
- `MAX_STEPS=5` and `num_ctx=8192` may be tight for complex multi-file tasks

---

## License

MIT
