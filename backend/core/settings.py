from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Optional

class Settings(BaseSettings):
    # Core Application Settings
    model_name: str = Field("gpt-oss:20b", env="MODEL_NAME")
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

    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        extra="ignore" # Ignore extra env vars
    )

# Instantiate settings
settings = Settings()
