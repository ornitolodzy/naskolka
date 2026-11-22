from __future__ import annotations

AI_DETECTED_THRESHOLD = 0.60
MANIPULATION_THRESHOLD = 0.40
SCAM_HIGH = 0.65
SCAM_ELEVATED = 0.35
LLM_SCAM_MIN = 0.6

LEVELS = {
    0: ("green", "Brak sygnałów oszustwa"),
    1: ("yellow", "Podejrzany materiał"),
    2: ("orange", "Wysokie ryzyko oszustwa: nowy lub nieprzypisany wzorzec"),
    3: ("red", "Część znanej kampanii oszustw"),
}

BAIT_TOPICS = {"investment", "health", "gambling", "giveaway_lottery", "government_benefit"}
TOPIC_PL = {
    "investment": "inwestycje / szybki zysk",
    "health": "zdrowie / suplementy",
    "gambling": "hazard",
    "giveaway_lottery": "loteria / nagrody",
    "government_benefit": "dopłaty / świadczenia",
}
_OWN_FACTORS = {"false_endorsement", "media_impersonation", "unrealistic_gain"}
MANIP_PL = {
    "urgency": "presja czasu",
    "secrecy_conspiracy": "sekret / spisek",
    "miracle_health": "cudowne leczenie",
    "fear_shock": "strach i szok",
    "authority_social_proof": "fałszywy autorytet",
    "official_benefit_bait": "przynęta „rządowej dopłaty”",
}


def ai_signal(features: dict, ai_score: float | None, analyst_labels: dict, detector_reliable: bool,
              propagated: list[dict]) -> dict:
    ai = features.get("ai") or {}
    declared = bool(ai.get("declared"))
    model_hit = ai_score is not None and ai_score >= AI_DETECTED_THRESHOLD and detector_reliable
    analyst = analyst_labels.get("ai")
    detected = model_hit or analyst == "true" or bool(propagated)
    if analyst == "false":
        detected = False
    if declared:
        status, text = "declared", "AI zadeklarowane w materiale"
    elif detected:
        status, text = "detected", "AI wykryte bez deklaracji"
    elif ai_score is not None and ai_score >= AI_DETECTED_THRESHOLD:
        status, text = "possible", f"detektor AI {ai_score:.2f} (model w nauce, tylko informacyjnie)"
    else:
        status, text = "none", "brak sygnału AI"
    return {
        "status": status,
        "text": text,
        "declared": declared,
        "detected": detected,
        "score": ai_score,
        "detector_reliable": detector_reliable,
        "propagated": propagated[:5],
        "declarations": [d["text"] for d in ai.get("declarations", [])][:5],
    }


def scam_assessment(features: dict, context: dict | None = None, ai: dict | None = None) -> dict:
    from .features.text import person_info

    context = context or {}
    ai = ai or {}
    factors: list[dict] = []

    def add(key: str, weight: float, label: str, detail: str) -> None:
        factors.append({"key": key, "weight": round(min(weight, 0.9), 3), "label": label, "detail": detail})

    topics = features.get("topics") or {}
    bait = [t for t, s in topics.items() if t in BAIT_TOPICS and s >= 0.25]
    persons = features.get("persons") or {}
    strong = [p for p, src in persons.items() if {"face", "image_name"} & set(src)]
    manip = features.get("manipulation") or {}
    cats = manip.get("categories") or {}
    contrib = manip.get("contributions") or {}

    if persons and bait:
        who = ", ".join(person_info(p)["name"] for p in (strong or list(persons))[:2])
        weight = 0.55 if strong else 0.30 if cats.get("unrealistic_gain") else 0.15
        add("false_endorsement", weight, "wizerunek osoby publicznej w reklamie finansowej / zdrowotnej",
            f"{who} ({'twarz na obrazie' if strong else 'nazwisko w treści'}) + {TOPIC_PL.get(bait[0], bait[0])}")
    if (ai.get("declared") or ai.get("detected")) and strong:
        add("deepfake", 0.45, "syntetyczny wizerunek osoby publicznej",
            f"{person_info(strong[0])['name']} + {ai.get('text', 'AI')}")
    elif ai.get("detected"):
        add("ai_undeclared", 0.30, "treść AI bez deklaracji", ai.get("text", ""))
    gains = cats.get("unrealistic_gain") or []
    if gains:
        add("money_promise", 0.30 + 0.07 * (len(gains) - 1), "obietnica łatwych pieniędzy",
            ", ".join(f"„{g}”" for g in gains[:3]))
    if cats.get("media_impersonation"):
        add("media_impersonation", 0.30, "podszywanie się pod redakcję lub medium", ", ".join(cats["media_impersonation"]))
    for cat, p in contrib.items():
        if cat not in _OWN_FACTORS:
            add(cat, p * 0.6, MANIP_PL.get(cat, cat), ", ".join(f"„{h}”" for h in cats.get(cat, [])[:3]))
    text_domains = list((features.get("tokens") or {}).get("text_domain") or {})
    if text_domains and (bait or gains):
        add("text_domain", 0.20, "adres strony podany w treści reklamy", ", ".join(text_domains[:3]))
    llm = features.get("narrative_llm") or {}
    try:
        llm_p = float(llm.get("oszustwo", 0))
    except (TypeError, ValueError):
        llm_p = 0.0
    if llm_p >= LLM_SCAM_MIN:
        detail = llm.get("schemat") or ""
        if llm.get("obietnica"):
            detail += f"; obietnica: {llm['obietnica']}"
        model = llm.get("model") or "LLM"
        name = "Bielik" if "bielik" in model.lower() else model.split(":")[0]
        add("llm", 0.35 * llm_p, f"ocena modelu językowego {name}: {llm_p:.2f}", detail.strip("; "))
    if context.get("reported"):
        add("reported", 0.40, "materiał ze zbioru zgłoszonych oszustw", "źródło: zbiór referencyjny / analityk")
    if context.get("scam_campaign"):
        peers = context["scam_campaign"]["peers"]
        add("known_campaign", 0.55, "twarde powiązanie ze zgłoszonymi oszustwami",
            f"kampania {context['scam_campaign']['id']}: {', '.join(peers[:4])}")
    elif context.get("scam_related"):
        add("related_campaign", 0.30, "techniczne podobieństwo do zgłoszonych oszustw",
            ", ".join(context["scam_related"][:4]))

    keep = 1.0
    for f in factors:
        keep *= 1 - f["weight"]
    score = round(1 - keep, 3)
    factors.sort(key=lambda f: -f["weight"])
    level = "high" if score >= SCAM_HIGH else "elevated" if score >= SCAM_ELEVATED else "low"
    return {
        "score": score,
        "level": level,
        "label": {"high": "wysokie", "elevated": "podwyższone", "low": "niskie"}[level],
        "factors": factors,
    }


def assess(
    features: dict,
    ai_score: float | None,
    analyst_labels: dict[str, str] | None = None,
    detector_reliable: bool = False,
    propagated: list[dict] | None = None,
    detector_trained: bool = False,
    context: dict | None = None,
) -> dict:
    from .features.text import person_info

    analyst_labels = analyst_labels or {}
    context = context or {}
    ai = ai_signal(features, ai_score, analyst_labels, detector_reliable, propagated or [])
    scam = scam_assessment(features, context, ai)
    analyst_scam = analyst_labels.get("scam")

    persons = features.get("persons") or {}
    strong = {k for k, v in persons.items() if {"face", "image_name"} & set(v)}
    manip = (features.get("manipulation") or {}).get("score", 0.0)

    reasons: list[str] = []
    if analyst_scam == "false":
        level = 0
        reasons.append("analityk oznaczył materiał jako niebędący oszustwem")
    elif context.get("scam_campaign"):
        level = 3
        sc = context["scam_campaign"]
        reasons.append(f"twarde ślady wspólne ze zgłoszonymi oszustwami w kampanii {sc['id']} "
                       f"({', '.join(sc['peers'][:4])})")
    elif scam["level"] == "high" or analyst_scam == "true":
        level = 2
        if analyst_scam == "true":
            reasons.append("analityk potwierdził oszustwo")
        reasons.append("brak twardego powiązania ze znaną kampanią: potencjalnie nowy wzorzec")
    elif scam["level"] == "elevated" or context.get("scam_related"):
        level = 1
    else:
        level = 0
    if level and analyst_scam != "false":
        reasons.extend(f"{f['label']}: {f['detail']}" for f in scam["factors"][:3] if f["key"] != "known_campaign")
    if level == 0 and analyst_scam != "false":
        reasons.append("brak czynników typowych dla oszustwa" if not scam["factors"]
                       else f"pojedyncze słabe sygnały (ryzyko {scam['score']:.2f})")
    if context.get("duplicates"):
        reasons.append(f"duplikat materiału {', '.join(sorted(context['duplicates'])[:3])}")

    color, label = LEVELS[level]
    return {
        "level": level,
        "color": color,
        "label": label,
        "reasons": reasons,
        "scam": scam,
        "ai": ai,
        "indicators": {
            "ai_declared": ai["declared"],
            "ai_score": ai_score,
            "ai_detector_reliable": detector_reliable,
            "ai_detected": ai["detected"],
            "ai_status": ai["status"],
            "ai_propagated": ai["propagated"],
            "public_person": bool(persons),
            "public_person_strong": bool(strong),
            "public_persons": [person_info(p)["name"] for p in persons][:4],
            "manipulation_score": manip,
            "manipulative": manip >= MANIPULATION_THRESHOLD,
            "known_campaign": (context.get("scam_campaign") or {}).get("id"),
            "duplicates": sorted(context.get("duplicates") or []),
            "analyst_scam": analyst_scam,
        },
    }
