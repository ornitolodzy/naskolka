from __future__ import annotations

import json
import logging

import httpx

from .config import settings

log = logging.getLogger(__name__)

_PROMPT = """Jesteś analitykiem dezinformacji. Oceń poniższy materiał z podejrzanej reklamy internetowej.
Zwróć WYŁĄCZNIE JSON o polach:
{{"narracja": "<1 zdanie: o czym jest i jaki ma cel>",
  "manipulacja": <liczba 0-1: jak mocno gra na emocjach, presji czasu, strachu, chciwości, autorytecie>,
  "techniki": ["<krótkie nazwy technik>"],
  "wezwanie_do_dzialania": "<co odbiorca ma zrobić, np. kliknąć, wpłacić, kupić>"}}

TYTUŁ: {title}
TREŚĆ (fragment):
{text}
"""


def available() -> bool:
    return bool(settings.ollama_url)


def ping() -> bool:
    if not available():
        return False
    try:
        return httpx.get(f"{settings.ollama_url}/api/tags", timeout=2).status_code == 200
    except httpx.HTTPError:
        return False


def analyze_narrative(title: str, text: str) -> dict | None:
    if not available():
        return None
    try:
        r = httpx.post(
            f"{settings.ollama_url}/api/generate",
            json={
                "model": settings.ollama_model,
                "prompt": _PROMPT.format(title=title[:300], text=text[:3500]),
                "format": "json",
                "stream": False,
                "options": {"temperature": 0.1, "num_ctx": 4096},
            },
            timeout=120,
        )
        r.raise_for_status()
        data = json.loads(r.json().get("response") or "{}")
        data["model"] = settings.ollama_model
        return data
    except (httpx.HTTPError, ValueError) as exc:
        log.warning("LLM narrative analysis failed: %s", exc)
        return None
