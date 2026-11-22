from __future__ import annotations

import ipaddress
import json
import logging
import mimetypes
import os
import re
import shutil
import socket
import threading
import time
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import httpx
import numpy as np

from . import correlate, llm, risk, seed
from .config import settings
from .features import asr, clip, faces, ocr
from .features.ai_detector import detector
from .features.text import fold, persons
from .ingest.collect import IMAGE_EXT, VIDEO_EXT, collect_artifacts, long_path
from .models import Material
from .pipeline import extract
from .store import Store

log = logging.getLogger(__name__)
_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
)


class Service:
    def __init__(self):
        for d in (settings.data_dir, settings.raw_dir, settings.uploads_dir, settings.cache_dir):
            d.mkdir(parents=True, exist_ok=True)
        self.store = Store(settings.db_path)
        self.pool = ThreadPoolExecutor(max_workers=int(os.getenv("FK_WORKERS", "2")))
        self._model: correlate.Model | None = None
        self._model_version = -1
        self._model_lock = threading.Lock()
        self._gallery: faces.Gallery | None = None
        self._gallery_lock = threading.Lock()
        self.import_state: dict = {"running": False}
        self.seed_state: dict = {"running": False}
        for row in self.store.all(with_features=False):
            if row["status"] in {"pending", "processing"}:
                self.submit(row["id"])

    def status(self) -> dict:
        return {
            "materials": len(self.store.all(with_features=False)),
            "modules": {
                "ocr": ocr.available(),
                "faces": faces.available(),
                "faces_gallery": self.gallery().summary() if faces.available() else {},
                "llm": {"configured": llm.available(), "reachable": llm.ping(), "model": settings.ollama_model},
                "online_enrichment": settings.enable_online,
                "asr": asr.info(),
                "clip": clip.info(),
                "ai_detector": detector.info(),
                "ai_seed": seed.summary() | {"job": self.seed_state},
            },
            "thresholds": {
                "campaign": correlate.CAMPAIGN_THRESHOLD,
                "family": correlate.FAMILY_THRESHOLD,
                "ai_detected": risk.AI_DETECTED_THRESHOLD,
                "manipulation": risk.MANIPULATION_THRESHOLD,
            },
            "import": self.import_state,
        }

    def gallery(self) -> faces.Gallery:
        with self._gallery_lock:
            if self._gallery is None:
                g = faces.Gallery()
                if faces.available():
                    try:
                        faces.load_curated_gallery(g)
                        self._bootstrap_gallery(g)
                    except Exception:
                        log.exception("gallery build failed")
                self._gallery = g
            return self._gallery

    def _bootstrap_gallery(self, g: faces.Gallery) -> None:
        import cv2

        for row in self.store.all(with_features=False):
            for art in row["artifacts"]:
                if art["kind"] not in {"page_image", "screenshot"}:
                    continue
                name = fold(art["name"].rsplit("/", 1)[-1].replace("-", " ").replace("_", " "))
                for p in persons():
                    if not p.pattern.search(name):
                        continue
                    bgr = cv2.imdecode(np.fromfile(art["path"], dtype=np.uint8), cv2.IMREAD_COLOR)
                    if bgr is None:
                        continue
                    found = faces.detect_and_embed(bgr, max_faces=1)
                    if found:
                        g.add(p.slug, found[0]["emb"], f"{row['id']}/{art['name']}")

    def submit(self, material_id: str):
        return self.pool.submit(self._process, material_id)

    def _process(self, material_id: str) -> None:
        m = self.store.material(material_id)
        if not m:
            return
        self.store.set_status(material_id, "processing")
        try:
            feats = extract(m, self.gallery() if faces.available() else None)
            if llm.available():
                nar = llm.analyze_narrative(feats["summary"]["title"], feats["text"]["body"])
                if nar:
                    feats["narrative_llm"] = nar
                    try:
                        llm_score = float(nar.get("manipulacja", 0))
                        lex = feats["manipulation"]["score"]
                        feats["manipulation"]["score"] = round(max(lex, 0.5 * lex + 0.5 * llm_score), 3)
                        feats["manipulation"]["method"] = "lexicon+llm"
                    except (TypeError, ValueError):
                        pass
            self.store.save_features(material_id, feats)
        except Exception as exc:
            log.exception("processing %s failed", material_id)
            self.store.set_status(material_id, "error", f"{type(exc).__name__}: {exc}")

    def reprocess_all(self) -> int:
        self._gallery = None
        rows = self.store.all(with_features=False)
        for r in rows:
            self.store.set_status(r["id"], "pending")
            self.submit(r["id"])
        return len(rows)

    @staticmethod
    def find_incident_dirs(root: Path) -> list[Path]:
        incidents: list[Path] = []
        for dirpath, dirs, files in os.walk(long_path(root)):
            dirs[:] = sorted(d for d in dirs if not d.startswith((".", "__")))
            real_files = [f for f in files if not f.startswith(".")]
            if len(dirs) >= 2 and not real_files:
                incidents.extend(Path(dirpath) / d for d in sorted(dirs, key=correlate._natural))
                dirs[:] = []
        return incidents

    def import_dataset(self, root: Path | None = None, zip_path: Path | None = None) -> dict:
        if self.import_state.get("running"):
            return self.import_state
        root = root or settings.raw_dir
        if zip_path:
            target = settings.raw_dir / zip_path.stem
            with zipfile.ZipFile(zip_path) as zf:
                zf.extractall(long_path(target))
            root = target
        incidents = self.find_incident_dirs(root)
        ids = []
        for d in incidents:
            mid = f"ds-{d.name}"
            arts = collect_artifacts(d)
            if not arts:
                continue
            self.store.upsert_material(
                Material(id=mid, label=f"Incydent {d.name}", source="dataset", root=str(d), artifacts=arts)
            )
            ids.append(mid)
        self._gallery = None
        self.import_state = {"running": True, "total": len(ids), "started_at": time.time(), "ids": ids}
        futures = [self.submit(mid) for mid in ids]

        def _watch():
            for f in futures:
                f.result()
            self.import_state["running"] = False
            self.import_state["finished_at"] = time.time()

        threading.Thread(target=_watch, daemon=True).start()
        return self.import_state

    def create_upload(self, files: list[tuple[str, bytes]], url: str | None, label: str | None) -> str:
        mid = f"up-{uuid.uuid4().hex[:8]}"
        root = settings.uploads_dir / mid
        root.mkdir(parents=True, exist_ok=True)
        for name, data in files:
            safe = re.sub(r"[^\w.\- ()\[\]ąćęłńóśźżĄĆĘŁŃÓŚŹŻ]", "_", Path(name).name)[:180] or "plik"
            target = root / safe
            target.write_bytes(data)
            if safe.lower().endswith(".zip"):
                with zipfile.ZipFile(target) as zf:
                    for member in zf.infolist():
                        dest = (root / member.filename).resolve()
                        if not str(dest).startswith(str(root.resolve())):
                            continue
                        zf.extract(member, long_path(root))
                target.unlink()
        warnings = []
        if url:
            try:
                self._fetch_url(url, root)
            except Exception as exc:
                warnings.append(f"Nie udało się pobrać strony {url}: {exc}")
                (root / "fetch_error.txt").write_text(str(exc), "utf-8")
        arts = collect_artifacts(root)
        m = Material(id=mid, label=label or (urlparse(url).hostname if url else files[0][0] if files else mid),
                     source="url" if url and not files else "upload", root=str(root), artifacts=arts, input_url=url)
        self.store.upsert_material(m)
        if warnings:
            self.store.set_label(mid, "fetch_warning", warnings[0])
        self.submit(mid)
        return mid

    @staticmethod
    def _check_public(host: str) -> None:
        for info in socket.getaddrinfo(host, None):
            ip = ipaddress.ip_address(info[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
                raise ValueError(f"adres {host} wskazuje na sieć prywatną")

    @staticmethod
    def _save_media(url: str, r: httpx.Response, root: Path) -> None:
        mime = r.headers.get("content-type", "").split(";")[0].strip().lower()
        kind = mime.split("/")[0]
        if kind not in {"image", "video"} or len(r.content) > settings.max_upload_mb * 1024 * 1024:
            return
        name = Path(urlparse(url).path).name
        name = re.sub(r"[^\w.\-]", "_", name)[:120] or "media"
        if Path(name).suffix.lower() not in IMAGE_EXT | VIDEO_EXT:
            name += mimetypes.guess_extension(mime) or (".jpg" if kind == "image" else ".mp4")
        (root / name).write_bytes(r.content)

    def _fetch_url(self, url: str, root: Path) -> None:
        u = urlparse(url)
        if u.scheme not in {"http", "https"} or not u.hostname:
            raise ValueError("niepoprawny adres URL")
        entries = []
        current = url
        with httpx.Client(timeout=15, headers={"User-Agent": _BROWSER_UA, "Accept-Language": "pl-PL,pl;q=0.9"}) as cl:
            for _ in range(8):
                host = urlparse(current).hostname or ""
                self._check_public(host)
                r = cl.get(current, follow_redirects=False)
                ip = socket.gethostbyname(host)
                loc = r.headers.get("location", "")
                body = r.text if "html" in r.headers.get("content-type", "") else ""
                entries.append({
                    "startedDateTime": datetime.now(timezone.utc).isoformat(),
                    "serverIPAddress": ip,
                    "request": {"method": "GET", "url": current},
                    "response": {
                        "status": r.status_code,
                        "redirectURL": str(httpx.URL(current).join(loc)) if loc else "",
                        "headers": [{"name": k, "value": v} for k, v in r.headers.items()],
                        "content": {"mimeType": r.headers.get("content-type", ""), "text": body},
                    },
                })
                if r.is_redirect and loc:
                    current = str(httpx.URL(current).join(loc))
                    continue
                if body:
                    (root / "page.html").write_text(f"<!-- saved from url=(0000){current} -->\n{body}", "utf-8")
                elif r.status_code == 200:
                    self._save_media(current, r, root)
                break
        (root / "fetched.har").write_text(json.dumps({"log": {"entries": entries}}), "utf-8")

    def model(self) -> correlate.Model:
        with self._model_lock:
            if self._model is None or self._model_version != self.store.version:
                version = self.store.version
                self._model = correlate.build(self.store.all())
                self._model_version = version
            return self._model

    def _declared_images(self) -> list[tuple[str, str, str]]:
        out = []
        for row in self.store.all():
            f = row.get("features") or {}
            srcs = set()
            for d in (f.get("ai") or {}).get("declarations", []):
                kind, _, src = d["source"].partition(":")
                if kind in {"metadata", "ocr", "exif"} and src:
                    srcs.add(src)
            out.extend((im["phash"], row["id"], im["src"]) for im in f.get("images", [])
                       if im["src"] in srcs and im.get("phash"))
        return out

    def propagated(self, row: dict, declared: list[tuple[str, str, str]]) -> list[dict]:
        from .ingest.media import hamming

        hits = []
        for im in (row.get("features") or {}).get("images", []):
            for ph, mid, src in declared:
                if mid == row["id"]:
                    continue
                d = hamming(im.get("phash", ""), ph)
                if d <= 6:
                    hits.append({"src": im["src"], "material": mid, "declared_src": src, "distance": d})
                    break
        return hits

    def lamp(self, row: dict, labels: dict, declared: list | None = None) -> dict | None:
        f = row.get("features")
        if not f:
            return None
        if (f.get("ai") or {}).get("declared"):
            prop = []
        else:
            prop = self.propagated(row, declared if declared is not None else self._declared_images())
        score = detector.score_vectors((f.get("ai") or {}).get("vectors") or [])
        return risk.assess(f, score, labels.get(row["id"]), detector.reliable, prop, detector.trained)

    def material_list(self) -> list[dict]:
        model = self.model()
        labels = self.store.labels()
        declared = self._declared_images()
        out = []
        for row in self.store.all():
            f = row.get("features") or {}
            out.append({
                "id": row["id"],
                "label": row["label"],
                "source": row["source"],
                "status": row["status"],
                "error": row["error"],
                "title": (f.get("summary") or {}).get("title"),
                "domains": (f.get("summary") or {}).get("landing_domains", []),
                "persons": list((f.get("persons") or {}).keys()),
                "topic": next(iter(f.get("topics") or {}), None),
                "campaign": model.material_campaign.get(row["id"]),
                "lamp": self.lamp(row, labels, declared),
                "thumbnail": self._thumbnail_index(row),
                "completeness": (f.get("completeness") or {}).get("score"),
            })
        return out

    @staticmethod
    def _thumbnail_index(row: dict) -> int | None:
        for kind in ("screenshot", "page_image"):
            for i, a in enumerate(row["artifacts"]):
                if a["kind"] == kind:
                    return i
        return None

    def material_view(self, mid: str) -> dict | None:
        row = self.store.get(mid)
        if not row:
            return None
        labels = self.store.labels()
        model = self.model()
        f = row.get("features") or {}
        if f:
            f = dict(f)
            vectors = (f.get("ai") or {}).get("vectors") or []
            f["ai"] = {k: v for k, v in (f.get("ai") or {}).items() if k != "vectors"}
            f["ai"]["image_scores"] = [
                {"src": s, "p": p} for s, p in sorted(detector.score_images(vectors), key=lambda x: -x[1])[:5]
            ]
            f["faces"] = [{k: v for k, v in face.items() if k != "emb"} for face in f.get("faces", [])]
            f["text"] = dict(f.get("text") or {})
            f["text"]["body"] = (f["text"].get("body") or "")[:6000]
        return {
            "id": row["id"],
            "label": row["label"],
            "source": row["source"],
            "status": row["status"],
            "error": row["error"],
            "input_url": row["input_url"],
            "artifacts": [{"index": i, "name": a["name"], "kind": a["kind"], "size": a["size"]}
                          for i, a in enumerate(row["artifacts"])],
            "features": f or None,
            "labels": labels.get(mid, {}),
            "lamp": self.lamp(row, labels),
            "assignment": correlate.assign(model, mid) if row.get("features") else None,
        }

    def artifact_path(self, mid: str, index: int) -> str | None:
        row = self.store.get(mid)
        if not row or not (0 <= index < len(row["artifacts"])):
            return None
        return row["artifacts"][index]["path"]

    def campaigns(self) -> dict:
        model = self.model()
        labels = self.store.labels()
        rows = {r["id"]: r for r in self.store.all()}
        declared = self._declared_images()
        out = []
        for c in model.campaigns:
            lamps = [self.lamp(rows[m], labels, declared) for m in c["members"] if m in rows]
            lamps = [l for l in lamps if l]
            c = dict(c)
            c["max_lamp"] = max(lamps, key=lambda l: l["level"]) if lamps else None
            c["titles"] = {m: ((rows[m].get("features") or {}).get("summary") or {}).get("title") for m in c["members"]}
            out.append(c)
        return {"campaigns": out, "families": model.families}

    def graph(self, min_score: float = 0.15) -> dict:
        model = self.model()
        labels = self.store.labels()
        rows = {r["id"]: r for r in self.store.all()}
        declared = self._declared_images()
        nodes = []
        for mid in model.ids:
            r = rows[mid]
            f = r.get("features") or {}
            lamp = self.lamp(r, labels, declared)
            nodes.append({
                "id": mid,
                "label": r["label"],
                "title": (f.get("summary") or {}).get("title"),
                "campaign": model.material_campaign.get(mid),
                "lamp": lamp["level"] if lamp else 0,
                "domains": (f.get("summary") or {}).get("landing_domains", []),
            })
        edges = []
        for (a, b), p in model.pairs.items():
            if p.score >= min_score:
                top = p.evidence[:3]
                edges.append({
                    "source": a, "target": b, "score": round(p.score, 3), "relation": p.relation,
                    "top": [f"{e.feature}: {e.value}" for e in top],
                    "channels": {k: round(v, 3) for k, v in p.channels.items()},
                })
        return {"nodes": nodes, "edges": edges,
                "thresholds": {"campaign": correlate.CAMPAIGN_THRESHOLD, "family": correlate.FAMILY_THRESHOLD}}

    def compare(self, a: str, b: str) -> dict | None:
        p = self.model().pair(a, b)
        return p.to_dict(top=60) if p else None

    def fetch_seed(self, shards: int) -> dict:
        if self.seed_state.get("running"):
            return self.seed_state

        def job():
            try:
                result = seed.fetch_openfake(shards=shards)
                self.seed_state.update(running=False, result=result, error=None, finished_at=time.time())
            except Exception as exc:
                log.exception("seed fetch failed")
                self.seed_state.update(running=False, error=f"{type(exc).__name__}: {exc}", finished_at=time.time())

        self.seed_state = {"running": True, "shards": shards, "started_at": time.time()}
        self.pool.submit(job)
        return self.seed_state

    def train_ai(self) -> dict:
        labels = self.store.labels()
        samples: list[tuple[dict, str, str]] = list(seed.load_samples())
        for row in self.store.all():
            f = row.get("features") or {}
            ai = f.get("ai") or {}
            lab = labels.get(row["id"], {}).get("ai")
            declared_srcs = set()
            whole = lab == "true"
            for d in ai.get("declarations", []):
                kind, _, src = d["source"].partition(":")
                if kind in {"metadata", "ocr", "exif"} and src:
                    declared_srcs.add(src)
                else:
                    whole = True
            for vec in ai.get("vectors") or []:
                if whole or vec["src"] in declared_srcs:
                    samples.append((vec, "pos", row["id"]))
                elif lab == "false":
                    samples.append((vec, "neg", row["id"]))
                else:
                    samples.append((vec, "unl", row["id"]))
        result = detector.train(samples)
        self.store.touch()
        return result

    def export(self) -> dict:
        model = self.model()
        rows = self.store.all()
        mats = []
        for r in rows:
            f = dict(r.get("features") or {})
            if f:
                f["ai"] = {k: v for k, v in (f.get("ai") or {}).items() if k != "vectors"}
                f["faces"] = [{k: v for k, v in x.items() if k != "emb"} for x in f.get("faces", [])]
            mats.append({"id": r["id"], "label": r["label"], "campaign": model.material_campaign.get(r["id"]),
                         "features": f})
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "materials": mats,
            "campaigns": model.campaigns,
            "families": model.families,
            "links": [p.to_dict(top=20) for p in model.pairs.values() if p.score >= correlate.FAMILY_THRESHOLD],
        }

    def delete(self, mid: str) -> bool:
        row = self.store.get(mid)
        ok = self.store.delete(mid)
        if ok and row and row["source"] != "dataset":
            shutil.rmtree(long_path(row["root"]), ignore_errors=True)
        return ok
