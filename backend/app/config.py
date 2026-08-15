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
    gemini_api_url: str = "https://generativelanguage.googleapis.com/v1beta/models"

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"

    openai_base_url: str = ""
    openai_model: str = ""
    openai_api_key: str = ""

    # NOAA SWPC data
    noaa_base_url: str = "https://services.swpc.noaa.gov/json"
    cache_ttl_seconds: int = 60

    # NOAA SWPC endpoint paths (relative to NOAA_BASE_URL)
    noaa_kp_path: str = "planetary_k_index_1m.json"
    noaa_mag_path: str = "rtsw/rtsw_mag_1m.json"
    noaa_wind_path: str = "rtsw/rtsw_wind_1m.json"
    noaa_proton_path: str = "goes/primary/integral-protons-6-hour.json"
    noaa_xray_path: str = "goes/primary/xray-flares-latest.json"

    # Copilot API route paths (API contract; override via .env when needed)
    route_root: str = "/"
    route_health: str = "/health"
    route_telemetry_latest: str = "/api/telemetry/latest"
    route_limits: str = "/api/limits"
    route_dose_forecast: str = "/api/dose/forecast"
    route_risk_assess: str = "/api/risk/assess"
    route_brief_generate: str = "/api/brief/generate"
    route_spe_alert: str = "/api/spe/alert"
    route_spe_forecast: str = "/api/spe/forecast"
    route_flux: str = "/api/telemetry/flux"
    route_kp: str = "/api/telemetry/kp"
    route_plan: str = "/api/plan"

    # SPE dose model: mSv per (pfu * hour); calibrated, see dose_engine.py
    spe_dose_coefficient: float = 2e-6

    cors_origins: str = "*"


@lru_cache
def get_settings() -> Settings:
    return Settings()
