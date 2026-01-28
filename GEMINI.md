# Local GPT Agent (`lokal-agent`)

## Project Overview
`lokal-agent` is a desktop-based local AI agent application designed to run entirely offline (or with controlled internet access) using `llama.cpp` and a custom Python backend. It integrates a globally accessible 20B+ parameter model (like GPT-OSS) to perform tasks ranging from chat to complex coding and analysis.

### Architecture
*   **UI (Frontend):** A desktop interface built with **PySide6** and **QtWebEngine**, rendering a local HTML/JS application (`ui/assets/index.html`).
*   **API (Backend):** A **Flask** server (`api_server.py`) running on `http://127.0.0.1:5000` that handles user requests, session management, and tool execution.
*   **Core Logic:** The `Agent` (`backend/core/agent.py`) manages the conversation loop, context, and decisions to use tools via a `Router`.
*   **LLM Backend:** A **llama.cpp** server running on `http://127.0.0.1:8080`, providing an OpenAI-compatible API for the agent.
*   **Database:** **SQLite** is used for storing conversation history and file metadata.

### Key Features
*   **Multi-Mode:** Supports specialized modes defined in `backend/modes/` (e.g., Chat, Coder, Analyst).
*   **Tooling:** Extensible tool system (`backend/tools/`) including:
    *   `file_loader`: Read/parse local files (PDF, DOCX, TXT).
    *   `python_exec`: Execute Python code safely.
    *   `sql_query`: Run SQL against the internal DB.
    *   `web_search`: Search the web (if enabled).
    *   `shell_exec`: Execute system shell commands.
    *   `image_analysis`: Analyze images.
    *   `planning`: Structured planning for complex tasks.

## Building and Running

### Prerequisites
*   Python 3.11+
*   `llama-server.exe` (from `llama.cpp` build)
*   A GGUF model file (e.g., `gpt-oss-20b.gguf`)

### Setup
1.  **Environment:**
    ```powershell
    python -m venv .venv
    .venv\Scripts\activate
    ```
2.  **Dependencies:**
    ```powershell
    pip install -r requirements.txt
    ```
3.  **Configuration:**
    *   Check `llama/scripts/run_server.ps1` to ensure `$Binary` points to your `llama-server.exe` and `$Model` points to your GGUF model.

### Execution
You need to run the components in the following order (typically in separate terminals):

1.  **Start LLM Server:**
    ```powershell
    ./llama/scripts/run_server.ps1
    ```
    *Ensure the server is running on port 8080.*

2.  **Start Backend API:**
    ```powershell
    python api_server.py
    ```
    *Runs on port 5000.*

3.  **Start UI:**
    ```powershell
    python main.py
    ```

## Development Conventions

*   **Directory Structure:**
    *   `backend/`: Contains all Python logic.
        *   `core/`: Core agent components (`Agent`, `Router`, `ContextManager`).
        *   `tools/`: Tool implementations. New tools should be added here and registered in `__init__.py`.
        *   `modes/`: JSON configurations for different agent personas.
        *   `database/`: DB schema and connection logic.
    *   `ui/`: Frontend assets (HTML/CSS/JS).
    *   `llama/`: Scripts and configs for the local LLM.
    *   `tests/`: Pytest suite.

*   **Code Style:**
    *   Use type hints (`from typing import ...`).
    *   Follow standard Python PEP 8 conventions.

*   **Testing:**
    *   Run tests using `pytest`:
        ```powershell
        pytest tests/
        ```
