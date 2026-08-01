from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Optional

class Settings(BaseSettings):
    # Core Application Settings
    model_name: str = Field("", env="MODEL_NAME")
    chainlit_database_url: Optional[str] = Field(None, env="CHAINLIT_DATABASE_URL")

    # ── Vision (image_analysis) — may use a different backend than the main LLM ─
    # Provider serving the vision model. Empty → follow llm_provider.
    vision_provider: str = Field("", env="VISION_PROVIDER")
    # OpenAI-compatible vision endpoint. Empty → follow openai_base_url
    # (e.g. the same llama-server launched with --mmproj serves text + vision).
    vision_base_url: str = Field("", env="VISION_BASE_URL")
    vision_api_key: Optional[str] = Field(None, env="VISION_API_KEY")
    # Vision model name/tag (Ollama tag, or the model llama-server reports).
    vision_model: str = Field("qwen3-vl:2b", env="VISION_MODEL")

    # ── LLM Provider ──────────────────────────────────────────────────────────
    # Which backend serves the models: "ollama" or "openai" (OpenAI-compatible,
    # e.g. llama.cpp's llama-server, LM Studio, vLLM, or the real OpenAI API).
    llm_provider: str = Field("ollama", env="LLM_PROVIDER")
    # Base URL for the OpenAI-compatible endpoint (used when llm_provider="openai").
    # llama.cpp default: http://localhost:8080/v1
    openai_base_url: str = Field("http://localhost:8080/v1", env="OPENAI_BASE_URL")
    # Model context window passed to the backend (Ollama). For llama.cpp this is
    # set at server launch with -c; keep them in sync.
    num_ctx: int = Field(16384, env="NUM_CTX")
    # Default sampling temperature (UI slider overrides this per-session).
    temperature: float = Field(0.7, env="TEMPERATURE")

    # Agent Parameters
    retry_count: int = Field(3, env="RETRY_COUNT")
    max_steps: int = Field(5, env="MAX_STEPS")

    # Ingestion: OCR is slow and only needed for scanned PDFs — off by default.
    ingest_ocr: bool = Field(False, env="INGEST_OCR")

    # Verbose hot-path logging (raw LLM output, tool args). Off by default.
    debug: bool = Field(False, env="DEBUG")
    
    # API Keys
    web_search_api_key: Optional[str] = Field(None, env="WEB_SEARCH_API_KEY")
    openai_api_key: Optional[str] = Field(None, env="OPENAI_API_KEY") # If used in future

    # Feature Flags (Optional)
    enable_multi_agent: bool = Field(False, env="ENABLE_MULTI_AGENT")

    # ── Sandbox (code / shell execution isolation) ────────────────────────────
    # "auto" uses Docker when available and falls back to in-process ("local");
    # "docker" forces Docker; "local" runs directly on the host (NOT isolated).
    sandbox_backend: str = Field("auto", env="SANDBOX_BACKEND")
    # Allow the sandbox container network access (needed for pip/npm/git installs,
    # but enables data exfiltration). Off by default.
    sandbox_allow_network: bool = Field(False, env="SANDBOX_ALLOW_NETWORK")
    sandbox_image: str = Field("localagent-sandbox:latest", env="SANDBOX_IMAGE")
    sandbox_memory: str = Field("2g", env="SANDBOX_MEMORY")
    sandbox_cpus: str = Field("2", env="SANDBOX_CPUS")
    sandbox_pids_limit: int = Field(256, env="SANDBOX_PIDS_LIMIT")

    # ── File-Editing Subsystem ────────────────────────────────────────────────
    # Root directory that the file-editing tools are allowed to read/write.
    file_edit_data_root: str = Field("data/exports", env="FILE_EDIT_DATA_ROOT")
    # Maximum content size per file (bytes). Default 200 KB.
    file_edit_max_file_size: int = Field(204_800, env="FILE_EDIT_MAX_FILE_SIZE")
    # Maximum number of files accepted in a single FileArchitect call.
    file_edit_max_files_per_call: int = Field(20, env="FILE_EDIT_MAX_FILES_PER_CALL")

    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        extra="ignore" # Ignore extra env vars
    )

# Instantiate settings
settings = Settings()
