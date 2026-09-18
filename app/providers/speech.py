import base64
from abc import ABC, abstractmethod

import httpx
from fastapi import HTTPException

from app.core.config import settings


class SpeechProvider(ABC):
    @abstractmethod
    def transcribe(self, audio: bytes, content_type: str, sample_rate_hertz: int | None = None) -> str: ...


class DisabledSpeechProvider(SpeechProvider):
    def transcribe(self, audio: bytes, content_type: str, sample_rate_hertz: int | None = None) -> str:
        raise HTTPException(503, "Speech provider is disabled")


class GoogleSpeechProvider(SpeechProvider):
    def transcribe(self, audio: bytes, content_type: str, sample_rate_hertz: int | None = None) -> str:
        if not settings.google_speech_api_key:
            raise HTTPException(503, "Google Speech is enabled but GOOGLE_SPEECH_API_KEY is not configured")
        encoding = "WEBM_OPUS" if "webm" in content_type else "LINEAR16"
        request = {
            "config": {
                "encoding": encoding,
                "languageCode": settings.google_speech_language_code,
                **({"sampleRateHertz": sample_rate_hertz} if sample_rate_hertz else {}),
            },
            "audio": {"content": base64.b64encode(audio).decode("ascii")},
        }
        try:
            response = httpx.post(
                "https://speech.googleapis.com/v1/speech:recognize",
                params={"key": settings.google_speech_api_key},
                json=request,
                timeout=60,
            )
            response.raise_for_status()
            results = response.json().get("results", [])
            transcript = " ".join(
                result["alternatives"][0]["transcript"]
                for result in results
                if result.get("alternatives")
            ).strip()
            if not transcript:
                raise HTTPException(422, "Google Speech returned no transcript")
            return transcript
        except HTTPException:
            raise
        except (httpx.HTTPError, KeyError, IndexError, TypeError) as exc:
            raise HTTPException(502, "Google Speech request failed") from exc


def get_speech_provider() -> SpeechProvider:
    mode = settings.speech_provider_mode.casefold()
    if mode in {"disabled", "off", "none"}:
        return DisabledSpeechProvider()
    if mode == "google":
        return GoogleSpeechProvider()
    raise HTTPException(500, f"Unsupported SPEECH_PROVIDER_MODE: {settings.speech_provider_mode}")
