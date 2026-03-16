from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Optional

class Settings(BaseSettings):
    # Core Application Settings
    model_name: str = Field("", env="MODEL_NAME")
    vision_model: str = Field("qwen3-vl:2b", env="VISION_MODEL")
    chainlit_database_url: Optional[str] = Field(None, env="CHAINLIT_DATABASE_URL")
    
    # Agent Parameters
    retry_count: int = Field(3, env="RETRY_COUNT")
    max_steps: int = Field(5, env="MAX_STEPS")
    
    # API Keys
    web_search_api_key: Optional[str] = Field(None, env="WEB_SEARCH_API_KEY")
    openai_api_key: Optional[str] = Field(None, env="OPENAI_API_KEY") # If used in future

    # Feature Flags (Optional)
    enable_multi_agent: bool = Field(False, env="ENABLE_MULTI_AGENT")

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
