"""OpenAI-compatible chat completions."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    base_url: str
    api_key: str
    model: str


def load_settings() -> Settings:
    _load_dotenv(ROOT / ".env")
    api_key = os.environ.get("LLM_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "LLM_API_KEY is missing. Copy .env.example to .env and set "
            "LLM_API_KEY, LLM_BASE_URL, and LLM_MODEL."
        )
    base_url = os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1").strip()
    model = os.environ.get("LLM_MODEL", "gpt-4o-mini").strip()
    if not base_url or not model:
        raise RuntimeError("LLM_BASE_URL and LLM_MODEL must be set.")
    return Settings(base_url=base_url.rstrip("/"), api_key=api_key, model=model)


async def complete(settings: Settings, messages: list[dict]) -> str:
    url = f"{settings.base_url}/chat/completions"
    try:
        async with httpx.AsyncClient(timeout=90) as client:
            response = await client.post(
                url,
                headers={"Authorization": f"Bearer {settings.api_key}"},
                json={
                    "model": settings.model,
                    "messages": messages,
                    "temperature": 0.2,
                },
            )
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text[:300]
        raise RuntimeError(
            f"The language model request failed ({exc.response.status_code}): {detail}"
        ) from exc
    except httpx.HTTPError as exc:
        raise RuntimeError(
            f"Could not reach the language model at {settings.base_url}."
        ) from exc

    payload = response.json()
    try:
        return payload["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, AttributeError) as exc:
        raise RuntimeError("The language model returned an unexpected response.") from exc


def _load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
