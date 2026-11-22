from functools import lru_cache
from typing import Literal

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    mode: Literal["deterministic", "langchain", "ollama"] = "deterministic"
    model: str = "openai:gpt-5.5"
    ollama_base_url: AnyHttpUrl = Field(default="http://127.0.0.1:11434")
    ollama_model: str = Field(default="qwen2.5:7b", min_length=1)
    ollama_timeout_seconds: float = Field(default=180, gt=0, le=600)
    max_tool_calls: int = 6
    require_approval_for_writes: bool = True

    model_config = SettingsConfigDict(env_prefix="AGENTMATRIX_", env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
