from __future__ import annotations

import hashlib
import json
import logging

import httpx

from .config import settings

log = logging.getLogger(__name__)

SCHEMES = [
    "fałszywa platforma inwestycyjna",
    "fałszywy artykuł lub wywiad z osobą publiczną",
    "cudowny lek lub suplement",
    "fałszywa dopłata lub program rządowy",
    "fałszywa loteria lub konkurs",
    "hazard lub kasyno",
    "fałszywy sklep lub promocja",
    "phishing lub przejęcie konta",
    "inne oszustwo",
    "brak oszustwa",
]

_EXAMPLE = {
    "streszczenie": "Reklama obiecuje szybki zysk z platformy inwestycyjnej, powołując się na znanego przedsiębiorcę.",
    "schemat": SCHEMES[0],
    "produkt": "nazwa platformy lub produktu albo pusty tekst",
    "obietnica": "np. 1000 zł tygodniowo",
    "podszywa_sie_pod": ["osoba lub marka"],
    "wezwanie_do_dzialania": "np. zarejestruj się i wpłać depozyt",
    "techniki": ["obietnica zysku", "autorytet"],
    "manipulacja": 0.8,
    "oszustwo": 0.9,
}

_PROMPT = """Jesteś analitykiem NASK badającym oszukańcze reklamy internetowe. Przeanalizuj materiał poniżej
(tekst strony, tekst odczytany z grafik przez OCR i transkrypcja mowy; OCR może sklejać słowa).

Odpowiedz WYŁĄCZNIE obiektem JSON z tymi samymi kluczami co w przykładzie, ale z wartościami dla TEGO materiału:
{example}

Zasady:
- "schemat" wybierz dokładnie jedną wartość z listy: {schemes}
- "manipulacja" i "oszustwo" to liczby od 0 do 1;
- "produkt" to nazwa własna platformy, aplikacji, leku lub sklepu, jeśli występuje, inaczej "";
- nie wymyślaj faktów, których nie ma w materiale.

TYTUŁ: {title}
MATERIAŁ:
{text}
"""


def available() -> bool:
    return bool(settings.ollama_url)


def ping() -> bool:
    if not available():
        return False
    try:
        return httpx.get(f"{settings.ollama_url}/api/tags", timeout=3).status_code == 200
    except httpx.HTTPError:
        return False


def _clamp(v) -> float:
    try:
        return max(0.0, min(1.0, float(v)))
    except (TypeError, ValueError):
        return 0.0


def _normalize(data: dict) -> dict | None:
    if not isinstance(data, dict) or "schemat" not in data:
        return None
    scheme = str(data.get("schemat") or "").strip().lower()
    data["schemat"] = next((s for s in SCHEMES if s == scheme), next((s for s in SCHEMES if scheme and scheme in s), "inne oszustwo"))
    for k in ("manipulacja", "oszustwo"):
        data[k] = _clamp(data.get(k))
    for k in ("podszywa_sie_pod", "techniki"):
        v = data.get(k) or []
        data[k] = [str(x)[:80] for x in (v if isinstance(v, list) else [v]) if x][:8]
    for k in ("streszczenie", "produkt", "obietnica", "wezwanie_do_dzialania"):
        data[k] = str(data.get(k) or "")[:300]
    product = data["produkt"].strip().lower()
    if (product in {"", "brak", "nazwa platformy lub produktu albo pusty tekst", "none", "null"}
            or any(w in product for w in ("nieznan", "brak nazwy", "nie podano")) or len(product.split()) > 4):
        data["produkt"] = ""
    data["narracja"] = data["streszczenie"]
    return data


def analyze_narrative(title: str, text: str) -> dict | None:
    if not available() or not (title or text).strip():
        return None
    prompt = _PROMPT.format(
        example=json.dumps(_EXAMPLE, ensure_ascii=False),
        schemes="; ".join(SCHEMES),
        title=(title or "")[:300],
        text=(text or "")[:5000],
    )
    key = hashlib.sha1(f"{settings.ollama_model}\n{prompt}".encode("utf-8")).hexdigest()
    cache = settings.cache_dir / "llm" / f"{key}.json"
    if cache.exists():
        try:
            cached = _normalize(json.loads(cache.read_text("utf-8")))
            if cached:
                return cached
        except ValueError:
            pass
    try:
        r = httpx.post(
            f"{settings.ollama_url}/api/generate",
            json={
                "model": settings.ollama_model,
                "prompt": prompt,
                "format": "json",
                "stream": False,
                "options": {"temperature": 0, "num_ctx": 4096},
            },
            timeout=180,
        )
        r.raise_for_status()
        data = _normalize(json.loads(r.json().get("response") or "{}"))
    except (httpx.HTTPError, ValueError) as exc:
        log.warning("LLM narrative analysis failed: %s", exc)
        return None
    if not data:
        return None
    data["model"] = settings.ollama_model
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(data, ensure_ascii=False), "utf-8")
    return data
