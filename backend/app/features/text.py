from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from ..config import settings

_PL = str.maketrans("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ", "acelnoszzACELNOSZZ")
_WS = re.compile(r"\s+")


def fold(text: str) -> str:
    t = unicodedata.normalize("NFC", text or "").translate(_PL)
    t = unicodedata.normalize("NFKD", t)
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    return _WS.sub(" ", t.lower()).strip()


@dataclass(frozen=True)
class Person:
    slug: str
    name: str
    role: str
    pattern: re.Pattern[str]


@lru_cache(maxsize=1)
def persons() -> list[Person]:
    data = yaml.safe_load(Path(settings.reference_dir, "persons.yaml").read_text("utf-8")) or []
    return [Person(p["slug"], p["name"], p.get("role", ""), re.compile(p["pattern"])) for p in data]


@lru_cache(maxsize=1)
def _lexicons() -> dict:
    raw = yaml.safe_load(Path(settings.reference_dir, "lexicons.yaml").read_text("utf-8"))
    return {
        "brands": {k: re.compile(v) for k, v in raw["brands"].items()},
        "topics": {k: [re.compile(p) for p in v] for k, v in raw["topics"].items()},
        "manipulation": {k: [re.compile(p) for p in v] for k, v in raw["manipulation"].items()},
        "ai": [re.compile(p) for p in raw["ai_declarations"]],
    }


def find_persons(folded: str) -> dict[str, int]:
    return {p.slug: n for p in persons() if (n := len(p.pattern.findall(folded)))}


def person_info(slug: str) -> dict[str, str]:
    for p in persons():
        if p.slug == slug:
            return {"slug": p.slug, "name": p.name, "role": p.role}
    return {"slug": slug, "name": slug, "role": ""}


def find_brands(folded: str) -> dict[str, int]:
    return {k: n for k, pat in _lexicons()["brands"].items() if (n := len(pat.findall(folded)))}


def topic_scores(folded: str) -> dict[str, float]:
    words = max(len(folded.split()), 1)
    scores = {}
    for topic, pats in _lexicons()["topics"].items():
        distinct = sum(1 for p in pats if p.search(folded))
        hits = sum(len(p.findall(folded)) for p in pats)
        if distinct:
            scores[topic] = round(min(1.0, distinct / 5) * 0.7 + min(1.0, hits * 200 / words / 10) * 0.3, 3)
    return dict(sorted(scores.items(), key=lambda kv: -kv[1]))


CATEGORY_WEIGHT = {
    "unrealistic_gain": 0.35,
    "miracle_health": 0.35,
    "official_benefit_bait": 0.30,
    "secrecy_conspiracy": 0.30,
    "urgency": 0.25,
    "fear_shock": 0.22,
    "authority_social_proof": 0.18,
    "false_endorsement": 0.45,
    "media_impersonation": 0.30,
}
BAIT_TOPICS = {"investment": "inwestycje", "health": "zdrowie", "gambling": "hazard",
               "giveaway_lottery": "loteria", "government_benefit": "dopłaty"}
MEDIA_BRANDS = {"gazeta.pl", "tvn24", "tvn", "polsat", "onet", "wp.pl", "interia", "rmf", "tvp", "money.pl",
                "business_insider", "forbes", "bankier", "rzeczpospolita", "super_express", "fakt"}


def _context_categories(persons: dict | None, topics: dict | None, brands: dict | None) -> dict[str, list[str]]:
    bait = [BAIT_TOPICS[t] for t, s in (topics or {}).items() if t in BAIT_TOPICS and s >= 0.25]
    out: dict[str, list[str]] = {}
    strong = [p for p, src in (persons or {}).items() if {"face", "image_name"} & set(src or [])]
    if strong and bait:
        out["false_endorsement"] = [f"{person_info(p)['name']} + {bait[0]}" for p in strong[:3]]
    media = sorted(set(brands or {}) & MEDIA_BRANDS)
    if media and bait:
        out["media_impersonation"] = [f"{m} + {bait[0]}" for m in media[:3]]
    return out


def manipulation_analysis(text: str, persons: dict | None = None, topics: dict | None = None,
                          brands: dict | None = None) -> dict:
    folded = fold(text)
    cats: dict[str, list[str]] = {}
    for cat, pats in _lexicons()["manipulation"].items():
        found: list[str] = []
        for p in pats:
            for m in p.finditer(folded):
                frag = m.group(0).strip()
                if frag not in found:
                    found.append(frag)
                if len(found) >= 6:
                    break
        if found:
            cats[cat] = found
    cats.update(_context_categories(persons, topics, brands))
    letters = [c for c in text if c.isalpha()]
    caps_ratio = (sum(c.isupper() for c in letters) / len(letters)) if letters else 0.0
    exclam = text.count("!")
    words = max(len(folded.split()), 1)
    style = min(1.0, (exclam * 100 / words) / 3) * 0.5 + min(1.0, max(0.0, caps_ratio - 0.15) * 4) * 0.5
    keep = 1.0
    contributions = {}
    for cat, hits in cats.items():
        p = min(0.6, CATEGORY_WEIGHT.get(cat, 0.2) * (1 + 0.15 * (len(hits) - 1)))
        contributions[cat] = round(p, 3)
        keep *= 1 - p
    if cats:
        keep *= 1 - 0.1 * style
    score = round(1 - keep, 3)
    return {
        "score": score,
        "categories": cats,
        "contributions": contributions,
        "exclamations": exclam,
        "caps_ratio": round(caps_ratio, 3),
        "method": "lexicon",
    }


def find_ai_declarations(text: str) -> list[str]:
    folded = fold(text)
    out: list[str] = []
    for p in _lexicons()["ai"]:
        for m in p.finditer(folded):
            frag = m.group(0).strip()
            if frag not in out:
                out.append(frag)
    return out


_STOP = set(
    fold(
        """a aby albo ale ani az bardzo bez bo by byc byl byla byli bylo co czy dla do gdy gdzie go i ich ile im
        ja jak jak jako je jego jej jest jestem jesli juz ktora ktore ktory ktorzy kto lub ma mam mi mnie moze
        na nad nam nas nie nic niz o od oraz po pod przez przy sa sie sobie tak tam ten to tu tych tylko ty
        w we wiec wszystko z za ze zeby jeszcze teraz kiedy bedzie tez ten ta te tego tej tym ktorej ktorego
        the and of to in is for on with you your that this are from be by or at an as it our we"""
    ).split()
)
_TOKEN = re.compile(r"[a-z][a-z0-9]{2,}")


def content_tokens(folded: str) -> list[str]:
    return [t for t in _TOKEN.findall(folded) if t not in _STOP]
