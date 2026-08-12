"""Application settings loaded from environment (.env)."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Radiation Copilot"
    version: str = "0.1.0"

    # LLM provider: gemini | ollama | openai
    llm_provider: str = "gemini"

    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"

    openai_base_url: str = ""
    openai_model: str = ""
    openai_api_key: str = ""

    # NOAA SWPC data
    noaa_base_url: str = "https://services.swpc.noaa.gov/json"
    cache_ttl_seconds: int = 60

    cors_origins: str = "*"


@lru_cache
def get_settings() -> Settings:
    return Settings()
