from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field

import networkx as nx
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from .features import faces as faces_mod
from .features.text import fold, person_info
from .ingest.media import hamming
from .models import Evidence

CAMPAIGN_THRESHOLD = 0.55
FAMILY_THRESHOLD = 0.30

FEATURES: dict[str, tuple[str, float, str]] = {
    "domain": ("infrastruktura", 0.97, "ta sama domena docelowa"),
    "aux_domain": ("infrastruktura", 0.80, "wspólna domena pomocnicza (tracker, API, CDN operatora)"),
    "text_domain": ("infrastruktura", 0.90, "ta sama domena podana w treści (napis na grafice, tekst, mowa)"),
    "ip": ("infrastruktura", 0.70, "ten sam adres IP serwera (poza wspólnym CDN)"),
    "ip_c": ("infrastruktura", 0.20, "ta sama podsieć /24"),
    "hosting": ("infrastruktura", 0.02, "ten sam dostawca CDN"),
    "server": ("infrastruktura", 0.04, "ten sam nagłówek serwera"),
    "tld": ("infrastruktura", 0.06, "ta sama domena najwyższego poziomu"),
    "registrar": ("infrastruktura", 0.12, "ten sam rejestrar domeny"),
    "nameserver": ("infrastruktura", 0.30, "te same serwery DNS"),
    "fb_pixel": ("śledzenie", 0.97, "ten sam Facebook Pixel"),
    "gtm": ("śledzenie", 0.95, "ten sam kontener Google Tag Manager"),
    "google_ads": ("śledzenie", 0.95, "to samo konto Google Ads"),
    "conversion_id": ("śledzenie", 0.95, "ten sam identyfikator konwersji Google"),
    "ga4": ("śledzenie", 0.95, "ta sama usługa Google Analytics 4"),
    "ua": ("śledzenie", 0.95, "ta sama usługa Universal Analytics"),
    "tiktok_pixel": ("śledzenie", 0.95, "ten sam TikTok Pixel"),
    "yandex_metrica": ("śledzenie", 0.95, "ten sam licznik Yandex Metrica"),
    "keitaro_like": ("śledzenie", 0.60, "ten sam identyfikator w trackerze ruchu"),
    "url_template": ("śledzenie", 0.85, "identyczny szablon linku śledzącego (te same parametry i kształt wartości)"),
    "url_param_keys": ("śledzenie", 0.40, "ten sam zestaw parametrów w linku"),
    "path_shape": ("śledzenie", 0.35, "ten sam kształt ścieżki URL"),
    "clickid_shape": ("śledzenie", 0.12, "identyfikatory kliknięć w tym samym formacie (typ trackera)"),
    "ad_account_prefix": ("śledzenie", 0.85, "ten sam prefiks konta reklamowego"),
    "ad_account_tag": ("śledzenie", 0.90, "to samo oznaczenie konta reklamowego"),
    "landing_id": ("śledzenie", 0.90, "ten sam identyfikator landing page w trackerze"),
    "tracker_campaign": ("śledzenie", 0.80, "ten sam identyfikator kampanii w trackerze"),
    "tracker_tag": ("śledzenie", 0.35, "ten sam znacznik trackera"),
    "lp_key": ("śledzenie", 0.90, "ten sam klucz landing page"),
    "utm_campaign": ("śledzenie", 0.55, "ta sama wartość utm_campaign"),
    "adset_name": ("śledzenie", 0.60, "ta sama nazwa zestawu reklam"),
    "ad_name": ("śledzenie", 0.60, "ta sama nazwa reklamy"),
    "traffic_source": ("śledzenie", 0.15, "to samo źródło ruchu w trackerze"),
    "tracker_user": ("śledzenie", 0.15, "ten sam użytkownik trackera"),
    "traffic_platform": ("śledzenie", 0.02, "ta sama platforma źródłowa"),
    "placement": ("śledzenie", 0.02, "to samo miejsce emisji"),
    "phone_pl": ("śledzenie", 0.90, "ten sam numer telefonu"),
    "email": ("śledzenie", 0.85, "ten sam adres e-mail"),
    "advertiser": ("śledzenie", 0.90, "ten sam reklamodawca (strona FB)"),
    "advertiser_id": ("śledzenie", 0.95, "ten sam identyfikator reklamodawcy"),
    "resource_sha1": ("kod strony", 0.75, "identyczny plik zasobu strony (JS/CSS/obraz)"),
    "resource_name": ("kod strony", 0.12, "ta sama nazwa pliku zasobu"),
    "script_name": ("kod strony", 0.18, "ta sama nazwa skryptu"),
    "html_class": ("kod strony", 0.035, "wspólna klasa CSS szablonu"),
    "html_id": ("kod strony", 0.05, "wspólny identyfikator elementu HTML"),
    "meta_generator": ("kod strony", 0.10, "ten sam generator strony"),
    "meta_site_name": ("kod strony", 0.45, "ta sama nazwa serwisu w metadanych"),
    "meta_author": ("kod strony", 0.35, "ten sam autor w metadanych"),
    "title": ("treść", 0.90, "identyczny tytuł strony"),
    "heading": ("treść", 0.45, "identyczny nagłówek"),
    "image_sha1": ("wizualne", 0.92, "identyczny plik graficzny"),
    "image_software": ("wizualne", 0.10, "ten sam program w metadanych obrazu"),
    "person": ("osoby i marki", 0.35, "ta sama osoba publiczna"),
    "brand": ("osoby i marki", 0.10, "ta sama marka / podszywanie się pod ten sam podmiot"),
    "topic": ("narracja", 0.15, "ta sama kategoria narracji"),
    "scheme": ("narracja", 0.15, "ten sam schemat oszustwa (ocena LLM)"),
    "product": ("treść", 0.60, "ta sama nazwa produktu lub platformy (ekstrakcja LLM)"),
}

HARD_CHANNELS = {"infrastruktura", "śledzenie", "kod strony", "treść", "wizualne"}

CHANNEL_CAP = {
    "infrastruktura": 0.97,
    "śledzenie": 0.97,
    "kod strony": 0.90,
    "treść": 0.92,
    "wizualne": 0.92,
    "twarze": 0.75,
    "osoby i marki": 0.40,
    "narracja": 0.15,
}

TOPIC_PL = {
    "investment": "inwestycje / szybki zysk",
    "health": "zdrowie / suplementy",
    "celebrity_news_bait": "fałszywy artykuł o celebrycie",
    "gambling": "hazard / gry",
    "giveaway_lottery": "loteria / nagrody",
    "government_benefit": "dopłaty / świadczenia",
}


def rarity(df: int, n: int) -> float:
    if df <= 2:
        r = 1.0
    else:
        r = (1 / (df - 1)) ** 0.5
    if n >= 6 and df / n > 0.5:
        r *= 0.3
    return r


def noisy_or(ps) -> float:
    acc = 1.0
    for p in ps:
        acc *= 1 - max(0.0, min(1.0, p))
    return 1 - acc


@dataclass
class Pair:
    a: str
    b: str
    score: float
    channels: dict[str, float]
    evidence: list[Evidence]
    relation: str = "unrelated"

    def to_dict(self, top: int = 12) -> dict:
        return {
            "a": self.a,
            "b": self.b,
            "score": round(self.score, 3),
            "relation": self.relation,
            "channels": {k: round(v, 3) for k, v in sorted(self.channels.items(), key=lambda kv: -kv[1])},
            "evidence": [e.to_dict() for e in self.evidence[:top]],
            "evidence_total": len(self.evidence),
        }


@dataclass
class Model:
    ids: list[str]
    pairs: dict[tuple[str, str], Pair]
    campaigns: list[dict]
    families: list[dict]
    material_campaign: dict[str, str]
    df: dict[str, Counter] = field(default_factory=dict)

    def pair(self, a: str, b: str) -> Pair | None:
        return self.pairs.get((a, b)) or self.pairs.get((b, a))

    def neighbours(self, mid: str, k: int = 8, min_score: float = 0.05) -> list[Pair]:
        out = [p for (a, b), p in self.pairs.items() if mid in (a, b) and p.score >= min_score]
        return sorted(out, key=lambda p: -p.score)[:k]


def _tfidf(docs: list[str]) -> np.ndarray | None:
    nonempty = [d for d in docs if len(d) > 200]
    if len(nonempty) < 2:
        return None
    vec = TfidfVectorizer(
        preprocessor=fold, ngram_range=(1, 2), min_df=1, max_df=0.85 if len(docs) > 4 else 1.0,
        sublinear_tf=True, max_features=60_000, token_pattern=r"(?u)\b[a-z][a-z0-9]{2,}\b",
    )
    try:
        X = vec.fit_transform([d if len(d) > 200 else "" for d in docs])
    except ValueError:
        return None
    return (X @ X.T).toarray()


def build(materials: list[dict]) -> Model:
    mats = [m for m in materials if m.get("features")]
    ids = [m["id"] for m in mats]
    n = len(mats)
    feats = {m["id"]: m["features"] for m in mats}

    df: dict[str, Counter] = defaultdict(Counter)
    for m in mats:
        for fname, vals in (m["features"].get("tokens") or {}).items():
            for v in vals:
                df[fname][v] += 1

    texts = [(f.get("text") or {}).get("body", "") + " " + " ".join(o["text"] for o in (f.get("text") or {}).get("ocr", []))
             for f in (feats[i] for i in ids)]
    sim_text = _tfidf(texts)

    img_index = _image_index(ids, feats)
    pairs: dict[tuple[str, str], Pair] = {}
    for i in range(n):
        for j in range(i + 1, n):
            a, b = ids[i], ids[j]
            p = _pair(a, b, feats[a], feats[b], df, n,
                      float(sim_text[i, j]) if sim_text is not None else 0.0, img_index)
            pairs[(a, b)] = p

    campaigns, families, mc = _cluster(ids, pairs, feats, df, n)
    return Model(ids=ids, pairs=pairs, campaigns=campaigns, families=families, material_campaign=mc, df=df)


def _image_index(ids, feats):
    out = {}
    for mid in ids:
        out[mid] = [(im["phash"], im["src"], im["kind"]) for im in feats[mid].get("images", []) if im.get("phash")]
    return out


def _pair(a, b, fa, fb, df, n, text_cos, img_index) -> Pair:
    ev: list[Evidence] = []
    ta, tb = fa.get("tokens") or {}, fb.get("tokens") or {}
    for fname, (channel, base, label) in FEATURES.items():
        va, vb = ta.get(fname), tb.get(fname)
        if not va or not vb:
            continue
        for v in set(va) & set(vb):
            w = base * rarity(df[fname][v], n)
            if w < 0.005:
                continue
            shown = person_info(v)["name"] if fname == "person" else v
            ev.append(Evidence(channel, fname, str(shown)[:160], w, f"{label} (występuje w {df[fname][v]} mat.)"))

    for x, y in ((ta, tb), (tb, ta)):
        for d in set(x.get("text_domain") or {}) & (set(y.get("domain") or {}) | set(y.get("aux_domain") or {})):
            w = 0.90 * rarity(df["text_domain"][d] + df["domain"][d] + df["aux_domain"][d], n)
            ev.append(Evidence("infrastruktura", "text_domain", d, w,
                               "domena podana w treści jednego materiału to domena strony drugiego"))

    if text_cos >= 0.25:
        w = min(0.9, (text_cos - 0.25) / 0.55 * 0.9)
        ev.append(Evidence("treść", "text_similarity", f"{text_cos:.2f}", w, "podobieństwo treści (TF-IDF, cosinus)"))

    matched = 0
    for ph_a, src_a, kind_a in img_index.get(a, []):
        best = None
        for ph_b, src_b, kind_b in img_index.get(b, []):
            d = hamming(ph_a, ph_b)
            if d <= 8 and (best is None or d < best[0]):
                best = (d, src_b)
        if best:
            matched += 1
            if matched > 6:
                break
            w = 0.85 if best[0] <= 4 else 0.55
            ev.append(Evidence("wizualne", "image_phash", f"{src_a.rsplit('/', 1)[-1][:60]} ≈ {best[1].rsplit('/', 1)[-1][:60]}",
                               w, f"wizualnie ten sam obraz (różnica pHash: {best[0]} bit)"))

    best_face = 0.0
    for f1 in fa.get("faces", []):
        for f2 in fb.get("faces", []):
            best_face = max(best_face, faces_mod.cosine(f1["emb"], f2["emb"]))
    if best_face >= faces_mod.SAME_FACE_THRESHOLD:
        w = min(0.75, 0.45 + (best_face - faces_mod.SAME_FACE_THRESHOLD) * 1.5)
        if set(ta.get("person", {})) & set(tb.get("person", {})):
            ev.append(Evidence("osoby i marki", "face", f"{best_face:.2f}", min(w, 0.30),
                               "ta sama twarz, prawdopodobnie wspólnej osoby publicznej"))
        else:
            ev.append(Evidence("twarze", "face", f"{best_face:.2f}", w,
                               "ta sama nieznana twarz w obu materiałach (SFace, cosinus)"))

    by_channel: dict[str, list[float]] = defaultdict(list)
    for e in ev:
        by_channel[e.channel].append(e.weight)
    channels = {c: min(CHANNEL_CAP.get(c, 0.9), noisy_or(ws)) for c, ws in by_channel.items()}
    score = noisy_or(channels.values())
    ev.sort(key=lambda e: -e.weight)

    relation = "unrelated"
    if score >= CAMPAIGN_THRESHOLD:
        relation = "variant"
        same_title = bool(set(ta.get("title", {})) & set(tb.get("title", {})))
        if text_cos >= 0.92 and (same_title or matched >= 3):
            relation = "duplicate"
    elif score >= FAMILY_THRESHOLD:
        relation = "related"
    return Pair(a, b, score, channels, ev, relation)


def _cluster(ids, pairs, feats, df, n):
    g = nx.Graph()
    g.add_nodes_from(ids)
    for (a, b), p in pairs.items():
        if p.score >= CAMPAIGN_THRESHOLD:
            g.add_edge(a, b, weight=p.score)

    groups: list[set[str]] = []
    for comp in nx.connected_components(g):
        if len(comp) > 6:
            sub = g.subgraph(comp)
            groups.extend(nx.community.louvain_communities(sub, weight="weight", seed=42, resolution=0.8))
        else:
            groups.append(set(comp))
    groups.sort(key=lambda s: (-len(s), min(s)))

    mc: dict[str, str] = {}
    campaigns = []
    for idx, members in enumerate(groups, start=1):
        cid = f"K{idx:02d}"
        for m in members:
            mc[m] = cid
        campaigns.append(_campaign_profile(cid, sorted(members, key=_natural), pairs, feats, df, n))

    cg = nx.Graph()
    cg.add_nodes_from(c["id"] for c in campaigns)
    links: dict[tuple[str, str], float] = {}
    for (a, b), p in pairs.items():
        ca, cb = mc[a], mc[b]
        if ca != cb and p.score >= FAMILY_THRESHOLD:
            key = tuple(sorted((ca, cb)))
            links[key] = max(links.get(key, 0), p.score)
    for (ca, cb), s in links.items():
        cg.add_edge(ca, cb, weight=s)
    families = []
    fam_idx = 0
    for comp in nx.connected_components(cg):
        if len(comp) < 2:
            continue
        fam_idx += 1
        fid = f"R{fam_idx:02d}"
        for c in campaigns:
            if c["id"] in comp:
                c["family"] = fid
        families.append({
            "id": fid,
            "campaigns": sorted(comp),
            "links": [{"a": a, "b": b, "score": round(s, 3)} for (a, b), s in links.items() if a in comp],
        })
    return campaigns, families, mc


def _natural(s: str):
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", s)]


def _campaign_profile(cid, members, pairs, feats, df, n) -> dict:
    shared: Counter = Counter()
    for fname in FEATURES:
        counts: Counter = Counter()
        for m in members:
            for v in (feats[m].get("tokens") or {}).get(fname, {}):
                counts[v] += 1
        for v, c in counts.items():
            if c >= 2 or len(members) == 1:
                shared[(fname, v)] = c
    signature = []
    for (fname, v), c in shared.items():
        channel, base, label = FEATURES[fname]
        w = base * rarity(df[fname][v], n)
        hidden = {"html_class", "html_id"} | ({"image_sha1", "resource_sha1"} if len(members) == 1 else set())
        if w >= 0.05 and fname not in hidden:
            shown = person_info(v)["name"] if fname == "person" else v
            signature.append({"feature": fname, "channel": channel, "value": shown, "label": label,
                              "members": c, "weight": round(w, 3)})
    signature.sort(key=lambda s: (-s["members"], -s["weight"]))

    persons = Counter(p for m in members for p in feats[m].get("persons", {}))
    brands = Counter(b for m in members for b in feats[m].get("brands", {}))
    topics = Counter(next(iter(feats[m].get("topics") or {"inne": 0})) for m in members)
    domains = sorted({d for m in members for d in feats[m]["summary"].get("landing_domains", [])})
    internal = [pairs.get((a, b)) or pairs.get((b, a)) for i, a in enumerate(members) for b in members[i + 1:]]
    internal = [p for p in internal if p]
    cohesion = round(sum(p.score for p in internal) / len(internal), 3) if internal else None

    topic = topics.most_common(1)[0][0]
    who = ", ".join(person_info(p)["name"] for p, _ in persons.most_common(2))
    name = TOPIC_PL.get(topic, "inne")
    if who:
        name += f" · {who}"
    elif brands:
        name += f" · {brands.most_common(1)[0][0]}"
    return {
        "id": cid,
        "name": name,
        "members": members,
        "size": len(members),
        "topic": topic,
        "persons": [person_info(p) | {"materials": c} for p, c in persons.most_common()],
        "brands": dict(brands.most_common()),
        "domains": domains,
        "signature": signature[:25],
        "cohesion": cohesion,
        "family": None,
    }


def assign(model: Model, mid: str, duplicates: set[str] | None = None) -> dict:
    duplicates = duplicates or set()
    neigh = model.neighbours(mid, k=5)
    cid = model.material_campaign.get(mid)
    camp = next((c for c in model.campaigns if c["id"] == cid), None)
    best = neigh[0] if neigh else None
    others = set(camp["members"]) - {mid} if camp else set()
    if duplicates and others and others <= duplicates:
        decision = "duplicate"
        text = (f"To ponowne zgłoszenie tego samego materiału ({', '.join(sorted(duplicates))}): ten sam adres "
                f"lub identyczne pliki. Poza duplikatami materiał nie pasuje do żadnej znanej kampanii.")
        camp = None
    elif camp and camp["size"] > 1:
        decision = "known_campaign"
        text = f"Materiał należy do kampanii {cid} ({camp['name']}), razem z {camp['size'] - 1} innymi materiałami."
    elif best and best.score >= FAMILY_THRESHOLD:
        other = best.b if best.a == mid else best.a
        decision = "related"
        text = (f"Brak wystarczających dowodów na tę samą kampanię, ale materiał jest podobny do {other} "
                f"(wynik {best.score:.2f}), więc to prawdopodobnie nowy wariant lub pokrewna kampania.")
    else:
        decision = "new_pattern"
        text = "Materiał nie pasuje do żadnej znanej kampanii. To potencjalnie nowy wzorzec działania."
    return {
        "decision": decision,
        "duplicates": sorted(duplicates),
        "campaign": cid if camp and camp["size"] > 1 else None,
        "family": camp.get("family") if camp else None,
        "explanation": text,
        "best_score": round(best.score, 3) if best else 0.0,
        "neighbours": [p.to_dict(top=8) for p in neigh],
    }
