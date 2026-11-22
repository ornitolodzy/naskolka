from __future__ import annotations

import json
import logging
import re
import time
from collections import Counter
from urllib.parse import urlparse

import imagehash
import numpy as np

from .config import settings
from .features import ai_detector, asr, clip, faces, ocr
from .features.infra import (
    RdapClient,
    find_trackers,
    is_public_cdn_host,
    text_domains,
    registrable_domain,
    shared_network,
    tld,
)
from .features.text import (
    content_tokens,
    find_ai_declarations,
    find_brands,
    find_persons,
    fold,
    manipulation_analysis,
    persons,
    topic_scores,
)
from .features.urls import url_features
from .ingest.har import parse_har
from .ingest.html import HtmlResult, mhtml_documents, parse_html
from .ingest.media import frame_to_image, image_info, video_frames
from .models import Material

log = logging.getLogger(__name__)

MAX_PAGE_IMAGES = 40
MAX_OCR_PAGE_IMAGES = 6
MAX_FACES = 24
_rdap = RdapClient(settings.cache_dir, settings.enable_online)


class Acc:

    def __init__(self):
        self.tokens: dict[str, Counter] = {}
        self.texts: list[tuple[str, str]] = []
        self.titles: list[str] = []
        self.headings: list[str] = []
        self.landing_urls: list[str] = []
        self.all_urls: set[str] = set()
        self.hosts: Counter = Counter()
        self.ips: dict[str, set[str]] = {}
        self.redirects: list[list[str]] = []
        self.servers: set[str] = set()
        self.trackers: dict[str, set[str]] = {}
        self.images: list[dict] = []
        self.ocr: list[dict] = []
        self.faces: list[dict] = []
        self.ai_vectors: list[dict] = []
        self.ai_decl: list[dict] = []
        self.meta_hints: list[dict] = []
        self.video: list[dict] = []
        self.transcripts: list[dict] = []
        self.meta: dict = {}
        self.warnings: list[str] = []
        self.kinds: Counter = Counter()

    def tok(self, name: str, value: str | None, n: int = 1) -> None:
        if value:
            self.tokens.setdefault(name, Counter())[str(value)[:200]] += n

    def add_trackers(self, found: dict[str, set[str]]) -> None:
        for k, vals in found.items():
            self.trackers.setdefault(k, set()).update(vals)


def _norm_title(t: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", fold(t))).strip()


def _add_html(acc: Acc, h: HtmlResult, source: str, page_url: str | None) -> None:
    if h.title:
        acc.titles.append(h.title)
        acc.tok("title", _norm_title(h.title))
    acc.headings.extend(h.headings[:30])
    for hd in h.headings[:30]:
        nt = _norm_title(hd)
        if len(nt) > 15:
            acc.tok("heading", nt)
    if h.text:
        acc.texts.append((source, h.text))
    if h.description:
        acc.texts.append((source + ":meta", h.description))
    url = page_url or h.saved_from
    if url and url.startswith("http"):
        acc.landing_urls.append(url)
    for key in ("generator", "og:site_name", "author"):
        if h.meta.get(key):
            acc.tok(f"meta_{key.replace('og:', '')}", fold(h.meta[key])[:80])
    for c in h.classes:
        acc.tok("html_class", c)
    for i in h.ids:
        acc.tok("html_id", i)
    for u in h.script_srcs:
        host = (urlparse(u).hostname or "").lower()
        name = urlparse(u).path.rsplit("/", 1)[-1].lower()
        if host and not is_public_cdn_host(host) and name.endswith(".js"):
            acc.tok("script_name", re.sub(r"[._-]?[0-9a-f]{8,}", "", name))
    for u in h.links + h.form_actions + h.iframe_srcs + h.script_srcs + h.image_srcs:
        acc.all_urls.add(u)
    acc.add_trackers(find_trackers(h.raw[:3_000_000]))


def _process_image(acc: Acc, path: str, src: str, kind: str, do_ocr: bool, gallery) -> None:
    res = image_info(path, src, kind)
    if res is None:
        return
    info, img = res
    acc.images.append(
        {"src": src, "kind": kind, "w": info.width, "h": info.height, "sha1": info.sha1,
         "phash": info.phash, "dhash": info.dhash}
    )
    acc.tok("image_sha1", info.sha1)
    if info.meta_hints:
        acc.meta_hints.append({"src": src, "hints": info.meta_hints})
    if info.software:
        acc.tok("image_software", fold(info.software))
        if decl := find_ai_declarations(info.software):
            acc.ai_decl.append({"source": f"exif:{src}", "text": decl[0]})

    mask: list[list[int]] = []
    if do_ocr:
        lines = ocr.ocr_image(img, cache_key=info.sha1)
        if lines:
            text = " ".join(l["text"] for l in lines)
            acc.ocr.append({"src": src, "text": text[:5000]})
            acc.texts.append((f"ocr:{src}", text))
            for l in lines:
                if decl := find_ai_declarations(l["text"]):
                    acc.ai_decl.append({"source": f"ocr:{src}", "text": decl[0], "box": l["box"]})
                    mask.append(l["box"])

    if img.width >= 128 and img.height >= 128:
        _add_ai_vector(acc, img, mask, src, kind)
    if faces.available() and len(acc.faces) < MAX_FACES:
        bgr = np.asarray(img)[:, :, ::-1].copy()
        _add_faces(acc, bgr, src, gallery)


def _add_ai_vector(acc: Acc, img, mask: list[list[int]], src: str, kind: str) -> None:
    masked = ai_detector.webify(ai_detector.mask_boxes(img, mask))
    entry = {"src": src, "kind": kind, "v": ai_detector.image_vector(masked)}
    if emb := clip.embed(masked):
        entry["c"] = emb
        entry["cm"] = clip.model_key()
    acc.ai_vectors.append(entry)


def _add_faces(acc: Acc, bgr: np.ndarray, src: str, gallery) -> None:
    for f in faces.detect_and_embed(bgr):
        if any(faces.cosine(f["emb"], g["emb"]) > 0.80 for g in acc.faces):
            continue
        match = gallery.match(f["emb"]) if gallery else None
        acc.faces.append(
            {"src": src, "bbox": f["bbox"], "score": f["score"],
             "emb": [round(float(x), 4) for x in f["emb"]],
             "match": {"slug": match[0], "sim": match[1]} if match else None}
        )
        if len(acc.faces) >= MAX_FACES:
            return


def _process_video(acc: Acc, path: str, src: str, gallery) -> None:
    frames, meta = video_frames(path, settings.video_frames)
    meta["src"] = src
    acc.video.append(meta)
    if asr.available():
        try:
            tr = asr.transcribe(path)
        except Exception as exc:
            log.exception("asr failed for %s", src)
            acc.warnings.append(f"wideo {src}: transkrypcja nieudana ({type(exc).__name__})")
            tr = None
        if tr and tr.get("text"):
            acc.transcripts.append({"src": src, "language": tr.get("language"), "duration": tr.get("duration"),
                                    "text": tr["text"][:20_000], "segments": tr.get("segments", [])[:400]})
            acc.texts.append((f"asr:{src}", tr["text"]))
            for decl in find_ai_declarations(tr["text"]):
                acc.ai_decl.append({"source": f"asr:{src}", "text": decl})
        elif tr and tr.get("no_audio"):
            meta["audio"] = False
    elif settings.enable_asr:
        acc.warnings.append(f"wideo {src}: brak transkrypcji mowy (moduł ASR niedostępny)")
    if not frames:
        acc.warnings.append(f"wideo {src}: {meta.get('error', 'brak klatek')}")
        return
    seen: list[str] = []
    for i, (ts, frame) in enumerate(frames):
        img = frame_to_image(frame)
        ph = str(imagehash.phash(img))
        if ph not in seen:
            seen.append(ph)
            acc.images.append({"src": f"{src}@{ts}s", "kind": "video_frame", "w": img.width, "h": img.height,
                               "sha1": "", "phash": ph, "dhash": str(imagehash.dhash(img))})
        mask: list[list[int]] = []
        if i % 3 == 0:
            lines = ocr.ocr_image(img, cache_key=f"v{ph}{i}")
            if lines:
                text = " ".join(l["text"] for l in lines)
                acc.ocr.append({"src": f"{src}@{ts}s", "text": text[:3000]})
                acc.texts.append((f"ocr:{src}", text))
                for l in lines:
                    if decl := find_ai_declarations(l["text"]):
                        acc.ai_decl.append({"source": f"ocr:{src}@{ts}s", "text": decl[0], "box": l["box"]})
                        mask.append(l["box"])
        _add_ai_vector(acc, img, mask, f"{src}@{ts}s", "video_frame")
        if faces.available() and len(acc.faces) < MAX_FACES:
            _add_faces(acc, frame, f"{src}@{ts}s", gallery)


def _process_meta(acc: Acc, path: str, name: str) -> None:
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        acc.warnings.append(f"nieczytelny plik metadanych {name}")
        return
    if name.endswith(".info.json"):
        adv = data.get("playlist_uploader") or data.get("uploader")
        adv_id = data.get("playlist_uploader_id") or data.get("uploader_id")
        acc.meta["ad"] = {
            "advertiser": adv,
            "advertiser_id": adv_id,
            "ad_library_url": data.get("webpage_url"),
            "ad_id": data.get("playlist_id") or data.get("id"),
            "title": data.get("title"),
            "description": (data.get("description") or "")[:2000],
            "extractor": data.get("extractor"),
        }
        acc.tok("advertiser", fold(adv) if adv else None)
        acc.tok("advertiser_id", adv_id)
        for k in ("title", "description"):
            if data.get(k):
                acc.texts.append((f"ad:{k}", data[k]))
    else:
        acc.meta["capture"] = {k: data.get(k) for k in ("tool", "captured_at", "page_url", "title")}
        if data.get("page_url"):
            acc.landing_urls.append(data["page_url"])
        if data.get("title"):
            acc.titles.append(data["title"])
            acc.tok("title", _norm_title(data["title"]))


def extract(material: Material, gallery=None) -> dict:
    t0 = time.time()
    acc = Acc()
    page_images = [a for a in material.artifacts if a.kind == "page_image"]
    page_images.sort(key=lambda a: -a.size)
    ocr_pages = {a.path for a in page_images[:MAX_OCR_PAGE_IMAGES]}

    for art in material.artifacts:
        acc.kinds[art.kind] += 1
        try:
            if art.kind == "meta":
                _process_meta(acc, art.path, art.name)
            elif art.kind == "har":
                har = parse_har(art.path)
                if har.landing_url:
                    acc.landing_urls.append(har.landing_url)
                acc.landing_urls.extend(har.document_urls[:5])
                acc.all_urls.update(har.urls)
                acc.hosts.update(har.hosts)
                for ip, hosts in har.ips.items():
                    acc.ips.setdefault(ip, set()).update(hosts)
                acc.redirects.extend([list(r) for r in har.redirects])
                acc.servers.update(har.server_headers)
                for sha, url in har.resource_hashes.items():
                    acc.tok("resource_sha1", sha)
                for name in har.resource_names:
                    acc.tok("resource_name", re.sub(r"[._-]?[0-9a-f]{8,}", "", name))
                for url, body in har.html_bodies[:5]:
                    _add_html(acc, parse_html(body, url), f"har:{art.name}", url)
                for _url, body in har.script_bodies:
                    acc.add_trackers(find_trackers(body))
                if har.failed:
                    acc.warnings.append(f"{art.name}: {har.failed}/{har.entries} żądań bez odpowiedzi")
            elif art.kind == "html":
                with open(art.path, encoding="utf-8", errors="replace") as fh:
                    raw = fh.read()
                _add_html(acc, parse_html(raw), f"html:{art.name}", None)
            elif art.kind == "mhtml":
                for loc, doc in mhtml_documents(art.path)[:3]:
                    _add_html(acc, parse_html(doc, loc), f"mhtml:{art.name}", loc)
            elif art.kind == "screenshot":
                _process_image(acc, art.path, art.name, "screenshot", True, gallery)
            elif art.kind == "page_image":
                if len([i for i in acc.images if i["kind"] == "page_image"]) < MAX_PAGE_IMAGES:
                    _process_image(acc, art.path, art.name, "page_image", art.path in ocr_pages, gallery)
            elif art.kind == "video":
                _process_video(acc, art.path, art.name, gallery)
        except Exception as exc:
            log.exception("artifact %s failed", art.name)
            acc.warnings.append(f"{art.name}: błąd przetwarzania ({type(exc).__name__})")

    if material.input_url:
        acc.landing_urls.insert(0, material.input_url)
    return _finalize(material, acc, time.time() - t0)


def _finalize(material: Material, acc: Acc, elapsed: float) -> dict:
    landing_domains: Counter = Counter()
    for u in acc.landing_urls:
        host = (urlparse(u).hostname or "").lower()
        if host and not is_public_cdn_host(host) and "." in host:
            landing_domains[registrable_domain(host)] += 1
    for d in landing_domains:
        acc.tok("domain", d)
        acc.tok("tld", tld(d))
    aux_domains = set()
    for host in acc.hosts:
        rd = registrable_domain(host)
        if host and "." in host and not is_public_cdn_host(host) and rd not in landing_domains:
            aux_domains.add(rd)
    for u in acc.all_urls:
        host = (urlparse(u).hostname or "").lower()
        rd = registrable_domain(host)
        if host and "." in host and not is_public_cdn_host(host) and rd not in landing_domains:
            aux_domains.add(rd)
    for d in aux_domains:
        acc.tok("aux_domain", d)

    ip_rows = []
    for ip, hosts in acc.ips.items():
        net = shared_network(ip)
        own = any(registrable_domain(h) in landing_domains for h in hosts)
        ip_rows.append({"ip": ip, "shared_network": net, "hosts": sorted(hosts), "landing": own})
        if own:
            if net:
                acc.tok("hosting", net)
            else:
                acc.tok("ip", ip)
                acc.tok("ip_c", ".".join(ip.split(".")[:3]) + ".0/24" if ip.count(".") == 3 else None)
    for s in acc.servers:
        acc.tok("server", s)

    rdap = {}
    for d in list(landing_domains)[:5]:
        info = _rdap.lookup(d)
        if info:
            rdap[d] = info
            if info.get("registrar"):
                acc.tok("registrar", fold(info["registrar"]))
            for ns in info.get("nameservers", []):
                acc.tok("nameserver", registrable_domain(ns))

    seen_urls = set()
    for u in acc.landing_urls + sorted(acc.all_urls):
        if u in seen_urls or "?" not in u:
            continue
        seen_urls.add(u)
        host = (urlparse(u).hostname or "").lower()
        if is_public_cdn_host(host):
            continue
        for k, vals in url_features(u).items():
            for v in vals:
                acc.tok(k, v)

    for kind, vals in acc.trackers.items():
        for v in vals:
            acc.tok(kind, v)

    body = "\n".join(t for _, t in acc.texts)
    folded = fold(body)
    title_text = " ".join(acc.titles + acc.headings[:10])
    person_hits = find_persons(fold(title_text + " " + body))
    person_sources: dict[str, set[str]] = {k: {"text"} for k in person_hits}
    for f in acc.faces:
        if f["match"]:
            person_sources.setdefault(f["match"]["slug"], set()).add("face")
    for img in acc.images:
        name = fold(img["src"].rsplit("/", 1)[-1].replace("-", " ").replace("_", " "))
        for p in persons():
            if p.pattern.search(name):
                person_sources.setdefault(p.slug, set()).add("image_name")
    for slug in person_sources:
        acc.tok("person", slug)
    brands = find_brands(folded)
    for b in brands:
        acc.tok("brand", b)
    topics = topic_scores(folded)
    if topics:
        acc.tok("topic", next(iter(topics)))

    manipulation = manipulation_analysis(title_text + "\n" + body[:60_000], person_sources, topics, brands)
    landing_set = set(landing_domains)
    for d in text_domains(body):
        if d not in landing_set:
            acc.tok("text_domain", d)
    decl_text = find_ai_declarations(title_text + " " + body)
    for d in decl_text:
        if not any(x["text"] == d for x in acc.ai_decl):
            acc.ai_decl.append({"source": "text", "text": d})
    for mh in acc.meta_hints:
        for h in mh["hints"]:
            if h.startswith(("iptc_", "generator_", "synthid", "c2pa")):
                acc.ai_decl.append({"source": f"metadata:{mh['src']}", "text": h})
    acc.ai_decl = list({(d["source"], d["text"]): d for d in acc.ai_decl}.values())

    keywords = [w for w, _ in Counter(content_tokens(folded)).most_common(40)]

    completeness = {
        "artifacts": dict(acc.kinds),
        "has_network_log": acc.kinds["har"] > 0,
        "has_page": acc.kinds["html"] + acc.kinds["mhtml"] > 0 or bool(acc.texts),
        "has_visual": acc.kinds["screenshot"] + acc.kinds["page_image"] + acc.kinds["video"] > 0,
        "has_video": acc.kinds["video"] > 0,
        "has_transcript": bool(acc.transcripts),
        "has_ad_metadata": "ad" in acc.meta,
        "warnings": acc.warnings,
    }
    missing = [k for k in ("has_network_log", "has_page", "has_visual") if not completeness[k]]
    completeness["score"] = round(1 - len(missing) / 3, 2)

    title = next((t for t in acc.titles if t), "") or (acc.meta.get("ad") or {}).get("title") or material.label
    return {
        "summary": {
            "title": title,
            "landing_url": acc.landing_urls[0] if acc.landing_urls else None,
            "landing_domains": sorted(landing_domains),
            "aux_domains": sorted(aux_domains),
            "text_chars": len(body),
            "images": len(acc.images),
            "faces": len(acc.faces),
            "elapsed_s": round(elapsed, 2),
        },
        "tokens": {k: dict(v) for k, v in acc.tokens.items()},
        "text": {
            "titles": list(dict.fromkeys(acc.titles))[:10],
            "headings": list(dict.fromkeys(acc.headings))[:30],
            "body": body[:40_000],
            "ocr": acc.ocr[:30],
            "transcripts": acc.transcripts,
            "keywords": keywords,
        },
        "persons": {k: sorted(v) for k, v in person_sources.items()},
        "brands": brands,
        "topics": topics,
        "manipulation": manipulation,
        "ai": {
            "declarations": acc.ai_decl[:20],
            "declared": bool(acc.ai_decl),
            "vectors": acc.ai_vectors[:40],
        },
        "faces": acc.faces,
        "images": acc.images[:120],
        "video": acc.video,
        "infra": {
            "hosts": dict(acc.hosts.most_common(60)),
            "ips": ip_rows[:60],
            "redirects": acc.redirects[:30],
            "servers": sorted(acc.servers)[:20],
            "rdap": rdap,
        },
        "trackers": {k: sorted(v) for k, v in acc.trackers.items()},
        "meta": acc.meta,
        "completeness": completeness,
    }
