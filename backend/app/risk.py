from __future__ import annotations

AI_DETECTED_THRESHOLD = 0.60
MANIPULATION_THRESHOLD = 0.40

LEVELS = {
    0: ("green", "Brak sygnałów AI"),
    1: ("yellow", "Zadeklarowano użycie AI: treść może być syntetyczna"),
    2: ("red", "Wykryto AI bez deklaracji: możliwe celowe wprowadzanie w błąd"),
    3: ("purple", "AI + wizerunek osoby publicznej"),
    4: ("black", "AI + osoba publiczna + manipulacyjna narracja"),
}


def assess(
    features: dict,
    ai_score: float | None,
    analyst_labels: dict[str, str] | None = None,
    detector_reliable: bool = False,
    propagated: list[dict] | None = None,
    detector_trained: bool = False,
) -> dict:
    analyst_labels = analyst_labels or {}
    propagated = propagated or []
    ai = features.get("ai") or {}
    declared = bool(ai.get("declared"))
    analyst_ai = analyst_labels.get("ai")
    model_hit = ai_score is not None and ai_score >= AI_DETECTED_THRESHOLD
    detected = (model_hit and detector_reliable) or analyst_ai == "true" or bool(propagated)

    persons = features.get("persons") or {}
    strong = {k: v for k, v in persons.items() if {"face", "image_name"} & set(v)}
    public_person = bool(persons)
    manip = (features.get("manipulation") or {}).get("score", 0.0)
    manipulative = manip >= MANIPULATION_THRESHOLD

    reasons: list[str] = []
    if declared:
        level = 1
        src = ", ".join(sorted({d["source"].split(":")[0] for d in ai.get("declarations", [])}))
        reasons.append(f"deklaracja AI znaleziona ({src})")
    elif detected:
        level = 2
        if propagated:
            p = propagated[0]
            reasons.append(
                f"obraz zadeklarowany jako AI w {p['material']} występuje tu bez deklaracji "
                f"({len(propagated)} obraz(y), różnica pHash {p['distance']} bit)"
            )
        if analyst_ai == "true":
            reasons.append("analityk oznaczył materiał jako AI")
        if model_hit and detector_reliable:
            reasons.append(f"detektor AI: {ai_score:.2f} ≥ {AI_DETECTED_THRESHOLD}, brak deklaracji")
    else:
        level = 0
        if ai_score is None and detector_trained:
            reasons.append("brak obrazów do oceny przez detektor AI")
        elif ai_score is None:
            reasons.append("detektor AI nie jest jeszcze wytrenowany (brak deklaracji do nauki)")
        elif not detector_reliable:
            reasons.append(f"detektor AI w trakcie nauki: wynik {ai_score:.2f} tylko informacyjnie")
        else:
            reasons.append(f"detektor AI: {ai_score:.2f} < {AI_DETECTED_THRESHOLD}")

    if level >= 1 and public_person:
        level = 3
        basis = "twarz / obraz" if strong else "wzmianka w treści"
        reasons.append(f"osoba publiczna ({basis})")
        if manipulative:
            level = 4
            reasons.append(f"narracja manipulacyjna (wynik {manip:.2f})")

    color, label = LEVELS[level]
    return {
        "level": level,
        "color": color,
        "label": label,
        "reasons": reasons,
        "indicators": {
            "ai_declared": declared,
            "ai_score": ai_score,
            "ai_detector_reliable": detector_reliable,
            "ai_detected": detected,
            "ai_propagated": propagated[:5],
            "public_person": public_person,
            "public_person_strong": bool(strong),
            "manipulation_score": manip,
            "manipulative": manipulative,
        },
    }
