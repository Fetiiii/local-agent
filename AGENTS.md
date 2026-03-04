  Must-follow constraints

- Strict JSON Contract: All agent outputs MUST strictly validate against AgentAction in backend/core/schemas.py.
- Parallel Execution: tool_calls is a list. Multiple independent tools (e.g., multiple web_search or web_scraper calls) MUST be grouped in a single turn to utilize the asyncio.gather parallel execution in agent_engine.py.
- Final Answer Logic: final_answer MUST be null if tool_calls contains any items. Never provide a final answer while tools are being executed.
- Stateful Python REPL: DataAnalystTool maintains a persistent self.globals dictionary. NEVER re-import libraries or re-initialize DataFrames (e.g., df) if they were defined in previous turns.
- Config Management: Use backend/core/settings.py (BaseSettings). DO NOT use os.getenv directly or hardcode constants.

  Validation before finishing

- Functional Check: Execute python test_all.py. It MUST pass for:
  - Data Analyst variable persistence across calls.
  - JSON Repair & Pydantic validation of broken LLM outputs.
  - ProjectScaffolder directory/file creation.
- Startup Check: Run chainlit run app.py to ensure Pydantic doesn't throw ValidationError on startup due to missing .env keys.

  Repo-specific conventions

- Tool Registration: Every new tool MUST be registered in app.py in TWO places: start() and on_chat_resume().
- Research Workflow:
       1. web_search: Returns ONLY metadata (titles/URLs).
       2. web_scraper: MUST be called to read the actual text content of a URL. Do not guess content from search snippets.
- Memory Management: Conversational history is tiered. MemoryManager automatically summarizes the buffer after max_recent_messages + 5. Do not manually truncate the history list.
- File System: All generated files, reports, or project structures MUST be saved under data/exports/ using ProjectScaffolderTool or FileWriterTool.

  Important locations

- backend/core/schemas.py: The definitive source for tool and agent JSON structures.
- backend/core/settings.py: Centralized Pydantic-Settings configuration.
- utils/agent_engine.py: Contains the asyncio.gather parallel execution loop and UI step management.
- backend/database/schema.sql: Contains the files table schema. Note: No auto-migrations; schema changes require manual SQL execution or DB reset.

  Change safety rules

- Backward Compatibility: When modifying AgentAction schema, ensure existing extract_json logic in helpers.py can still parse older message formats stored in data/temp/chainlit.db.
- Path Safety: Tools writing to disk (Scaffolder, Writer) MUST use os.path.basename or validate that paths do not contain .. to prevent directory traversal.
- RAG Integrity: Do not modify UniversalIngestor parsers without verifying they still output valid Markdown, as the RAG search depends on Markdown structure for chunking.

  Known gotchas

- Ollama JSON Mode: Ollama's format="json" can sometimes fail on very large responses. The extract_json helper uses json_repair to recover these.
- Matplotlib Backend: DataAnalystTool uses matplotlib.use('Agg'). GUI-based plt.show() calls will fail or be ignored; plots MUST be saved to data/temp/plots/.
- Thread Safety: While tool execution is parallel via asyncio, the DataAnalystTool shares a single global state. Sequential dependency within a single parallel batch will fail.
