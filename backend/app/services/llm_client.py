"""Provider-agnostic LLM client.

Interface: ``LLMClient.generate(system, user) -> str``

Providers (selected via LLM_PROVIDER env):
  - gemini  : Google AI Studio free tier (generativelanguage.googleapis.com)
  - ollama  : local, offline (OpenAI-compatible /v1/chat/completions)
  - openai  : any OpenAI-compatible endpoint (e.g. LiteLLM local proxy)

The app only ever talks to one of these; swapping is a config change, not a
code change. This is the seam Marc approved: no third-party dependency baked
into the app itself.
"""
import abc
from typing import Optional

import httpx

from app.config import get_settings


class LLMClient(abc.ABC):
    provider: str = "abstract"

    @abc.abstractmethod
    async def generate(self, system: str, user: str) -> str:
        """Return generated text for (system, user) prompt pair."""


class GeminiClient(LLMClient):
    provider = "gemini"

    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model
        self.api_url = get_settings().gemini_api_url.rstrip("/")

    async def generate(self, system: str, user: str) -> str:
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is not set")
        url = f"{self.api_url}/{self.model}:generateContent"
        payload = {
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"temperature": 0.4, "maxOutputTokens": 900},
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, params={"key": self.api_key}, json=payload)
            resp.raise_for_status()
            data = resp.json()
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except (KeyError, IndexError):
            raise RuntimeError(f"Unexpected Gemini response: {data}")


class OllamaClient(LLMClient):
    provider = "ollama"

    def __init__(self, base_url: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.model = model

    async def generate(self, system: str, user: str) -> str:
        url = f"{self.base_url}/v1/chat/completions"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.4,
            "max_tokens": 900,
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
        return data["choices"][0]["message"]["content"].strip()


class OpenAICompatibleClient(LLMClient):
    provider = "openai"

    def __init__(self, base_url: str, model: str, api_key: str = ""):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key

    async def generate(self, system: str, user: str) -> str:
        if not self.model:
            raise RuntimeError("OPENAI_MODEL is not set")
        url = f"{self.base_url}/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.4,
            "max_tokens": 900,
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        return data["choices"][0]["message"]["content"].strip()


def get_llm_client() -> Optional[LLMClient]:
    """Factory. Returns None when the configured provider is unavailable."""
    s = get_settings()
    provider = s.llm_provider.lower()
    try:
        if provider == "gemini":
            return GeminiClient(s.gemini_api_key, s.gemini_model)
        if provider == "ollama":
            return OllamaClient(s.ollama_base_url, s.ollama_model)
        if provider == "openai":
            return OpenAICompatibleClient(s.openai_base_url, s.openai_model, s.openai_api_key)
    except Exception:
        return None
    return None
