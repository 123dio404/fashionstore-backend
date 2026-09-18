import json
from abc import ABC, abstractmethod

import httpx
from fastapi import HTTPException

from app.core.config import settings


class AIProvider(ABC):
    @abstractmethod
    def generate_text(self, prompt: str) -> str: ...

    def generate_json(self, prompt: str) -> dict:
        text = self.generate_text(
            f"{prompt}\nReturn only a valid JSON object, without markdown fences."
        )
        try:
            return json.loads(text)
        except (TypeError, json.JSONDecodeError) as exc:
            raise HTTPException(502, "AI provider returned invalid JSON") from exc


class DisabledAIProvider(AIProvider):
    def generate_text(self, prompt: str) -> str:
        raise HTTPException(503, "AI provider is disabled")


class GeminiProvider(AIProvider):
    def generate_text(self, prompt: str) -> str:
        if not settings.gemini_api_key:
            raise HTTPException(503, "Gemini is enabled but GEMINI_API_KEY is not configured")
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{settings.gemini_model}:generateContent"
        )
        try:
            response = httpx.post(
                url,
                params={"key": settings.gemini_api_key},
                json={"contents": [{"parts": [{"text": prompt}]}]},
                timeout=30,
            )
            response.raise_for_status()
            payload = response.json()
            return payload["candidates"][0]["content"]["parts"][0]["text"]
        except (httpx.HTTPError, KeyError, IndexError, TypeError) as exc:
            raise HTTPException(502, "Gemini request failed") from exc


def get_ai_provider() -> AIProvider:
    mode = settings.ai_provider_mode.casefold()
    if mode in {"disabled", "off", "none"}:
        return DisabledAIProvider()
    if mode == "gemini":
        return GeminiProvider()
    raise HTTPException(500, f"Unsupported AI_PROVIDER_MODE: {settings.ai_provider_mode}")
