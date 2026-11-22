import json

from app import correlate, risk
from app.features.infra import find_trackers, registrable_domain, shared_network
from app.features.text import find_ai_declarations, find_persons, fold, manipulation_analysis
from app.features.urls import url_features, value_shape
from app.ingest.har import parse_har
from app.service import Service


def test_value_shape_and_url_template_survive_domain_rotation():
    a = url_features("https://civicdaybook.live/?utm_id=WVVfDj0sSpk725CZefaO&utm_medium=7DJYmtt5h2&utm_campaign=5DkJlRt5Wj")
    b = url_features("https://acrosscommunities.live/?utm_id=MKjnwCwp0KZrQEO7LbGe&utm_medium=HhmfRsguVp&utm_campaign=TEnLRFoNbq")
    assert a["url_template"] == b["url_template"]
    assert value_shape("120250558396250564") == "D18"
    assert value_shape("db6apl4o0bqs73b1b7a0") == "Lx20"


def test_ad_account_prefix_and_pixel_from_query():
    f = url_features("https://x.top/?pxl=1071875908635809&acc=hk77_tv6_feed&land_id=23501&ad_id=1")
    assert f["fb_pixel"] == {"1071875908635809"}
    assert f["ad_account_prefix"] == {"hk77"}
    assert f["landing_id"] == {"23501"}


def test_infra_helpers():
    assert registrable_domain("bf1.clickline.org") == "clickline.org"
    assert shared_network("188.114.96.12") == "cloudflare"
    assert shared_network("10.0.0.1") is None
    t = find_trackers("fbq('init', '1549107073347817'); gtag('config','AW-18463917747'); css-1@mhtml.blink")
    assert t["fb_pixel"] == {"1549107073347817"}
    assert t["google_ads"] == {"AW-18463917747"}
    assert "email" not in t


def test_text_lexicons():
    folded = fold("«Wiem, kto strzelał»: zamach na Rafała Brzoskę, założyciela InPostu")
    assert "rafal-brzoska" in find_persons(folded)
    m = manipulation_analysis("SZOK! Nagranie usunięto przed północą. Tylko dziś zarobisz 5000 zł dziennie bez ryzyka!")
    assert m["score"] >= 0.4
    assert {"urgency", "unrealistic_gain"} <= set(m["categories"])
    assert find_ai_declarations("Ten obraz został wygenerowany przy użyciu AI")
    assert not find_ai_declarations("Zwykły artykuł o gospodarce")
    assert not find_ai_declarations("Platforma oparta na sztucznej inteligencji zarabia za ciebie")


def test_transcript_style_manipulation():
    m = manipulation_analysis(
        "Program państwowy pokrywa 50% kosztów dla wszystkich emerytów. Leczenie bez zastrzyków. "
        "Przestańcie odkładać leczenie, w przeciwnym razie wylądujesz na wózku inwalidzkim. "
        "Kliknij w poniższy link, dopóki trwa program."
    )
    assert {"official_benefit_bait", "urgency", "miracle_health", "fear_shock"} <= set(m["categories"])
    assert m["score"] >= 0.5
    assert "fear_shock" not in manipulation_analysis("Producent wózków inwalidzkich otworzył fabrykę")["categories"]


def _fake_samples(rng, n, label, source, shift):
    import numpy as np

    out = []
    for _ in range(n):
        v = rng.normal(0, 1, 23) + shift
        c = rng.normal(0, 1, 16) + shift
        c = c / np.linalg.norm(c)
        out.append(({"src": "x", "v": v.tolist(), "c": c.tolist(), "cm": "test"}, label, source))
    return out


def test_ai_detector_gate_requires_generalization_and_no_domain_shift(tmp_path, monkeypatch):
    import numpy as np

    from app.features import ai_detector

    monkeypatch.setattr(ai_detector, "_model_path", lambda: tmp_path / "head.json")
    rng = np.random.default_rng(0)
    pos = [s for g in range(6) for s in _fake_samples(rng, 10, "pos", f"seed:ai/gen{g}", 1.5)]
    neg = _fake_samples(rng, 60, "neg", "seed:real/photos", 0.0)

    det = ai_detector.AIDetector()
    det.train(pos + neg + _fake_samples(rng, 40, "unl", "ds-1", 0.0))
    assert det.model["mode"] == "supervised"
    assert det.model["heldout_auc"] >= 0.8
    assert det.reliable

    det.train(pos + neg + _fake_samples(rng, 40, "unl", "ds-1", 3.0))
    assert det.model["unlabeled_flag_rate"] > ai_detector.MAX_UNLABELED_FLAG_RATE
    assert not det.reliable

    det.train(pos[:7] + _fake_samples(rng, 40, "unl", "ds-1", 0.0))
    assert det.model["mode"] == "pu"
    assert not det.reliable


def test_rarity_damps_common_values():
    assert correlate.rarity(2, 10) == 1.0
    assert correlate.rarity(8, 10) < 0.15


def _mat(mid, **tokens):
    return {"id": mid, "features": {"tokens": {k: {v: 1 for v in vals} for k, vals in tokens.items()},
                                    "summary": {"landing_domains": tokens.get("domain", [])},
                                    "text": {"body": ""}, "images": [], "faces": [], "persons": {}, "topics": {}}}


def test_soft_evidence_alone_never_makes_a_campaign():
    mats = [_mat("a", person=["monika-olejnik"], brand=["mbank", "pekao", "santander"], topic=["investment"]),
            _mat("b", person=["monika-olejnik"], brand=["mbank", "pekao", "santander"], topic=["investment"]),
            *[_mat(f"x{i}", domain=[f"d{i}.com"]) for i in range(5)]]
    model = correlate.build(mats)
    assert model.pair("a", "b").score < correlate.CAMPAIGN_THRESHOLD
    assert model.material_campaign["a"] != model.material_campaign["b"]


def test_hard_evidence_links_and_explains():
    mats = [_mat("a", fb_pixel=["123456789012"], domain=["one.live"]),
            _mat("b", fb_pixel=["123456789012"], domain=["two.live"]),
            _mat("c", domain=["three.live"])]
    model = correlate.build(mats)
    p = model.pair("a", "b")
    assert p.score >= correlate.CAMPAIGN_THRESHOLD
    assert p.evidence[0].feature == "fb_pixel"
    assert model.material_campaign["a"] == model.material_campaign["b"] != model.material_campaign["c"]
    assert correlate.assign(model, "c")["decision"] == "new_pattern"


def test_risk_escalation_chain():
    base = {"ai": {"declared": False}, "persons": {}, "manipulation": {"score": 0.0}}
    assert risk.assess(base, None)["level"] == 0
    declared = base | {"ai": {"declared": True, "declarations": [{"source": "ocr:x.png", "text": "ai"}]}}
    assert risk.assess(declared, None)["level"] == 1
    assert risk.assess(base, 0.9, detector_reliable=True)["level"] == 2
    assert risk.assess(base, 0.9, detector_reliable=False)["level"] == 0
    prop = [{"src": "a.jpg", "material": "ds-61", "declared_src": "b.jpg", "distance": 2}]
    assert risk.assess(base, None, propagated=prop)["level"] == 2
    celeb = declared | {"persons": {"monika-olejnik": ["face"]}}
    assert risk.assess(celeb, None)["level"] == 3
    assert risk.assess(celeb | {"manipulation": {"score": 0.7}}, None)["level"] == 4
    assert risk.assess(base | {"persons": {"x": ["text"]}, "manipulation": {"score": 0.9}}, None)["level"] == 0


def test_har_parsing(tmp_path):
    har = {"log": {"entries": [
        {"startedDateTime": "2026-01-01T00:00:01Z", "serverIPAddress": "188.114.96.12",
         "request": {"url": "https://scam.live/?utm_id=a"},
         "response": {"status": 200, "headers": [{"name": "server", "value": "cloudflare"}],
                      "content": {"mimeType": "text/html", "text": "<html><title>T</title><body>x</body></html>"}}},
        {"startedDateTime": "2026-01-01T00:00:00Z", "request": {"url": "https://ads.example/r"},
         "response": {"status": 302, "redirectURL": "https://scam.live/?utm_id=a", "headers": [], "content": {}}},
    ]}}
    p = tmp_path / "x.har"
    p.write_text(json.dumps(har), "utf-8")
    r = parse_har(str(p))
    assert r.landing_url == "https://scam.live/?utm_id=a"
    assert r.redirects == [("https://ads.example/r", "https://scam.live/?utm_id=a")]
    assert "server:cloudflare" in r.server_headers


def test_incident_discovery(tmp_path):
    root = tmp_path / "raw" / "do_udostepnienia"
    for name in ("1", "2", "10"):
        (root / name).mkdir(parents=True)
        (root / name / "a.html").write_text("<html></html>")
    found = [p.name for p in Service.find_incident_dirs(tmp_path / "raw")]
    assert found == ["1", "2", "10"]
