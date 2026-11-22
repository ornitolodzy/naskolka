from __future__ import annotations

import logging
import threading
import urllib.request
from pathlib import Path

import numpy as np

from ..config import settings

log = logging.getLogger(__name__)

MODELS = {
    "detector": (
        "face_detection_yunet_2023mar.onnx",
        "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
    ),
    "recognizer": (
        "face_recognition_sface_2021dec.onnx",
        "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx",
    ),
}
MATCH_THRESHOLD = 0.40
SAME_FACE_THRESHOLD = 0.45
MIN_FACE_PX = 48

_lock = threading.Lock()
_state: dict = {"det": None, "rec": None, "error": None}


def models_dir() -> Path:
    p = settings.data_dir / "models"
    p.mkdir(parents=True, exist_ok=True)
    return p


def ensure_models(download: bool = True) -> bool:
    for fname, url in MODELS.values():
        target = models_dir() / fname
        if target.exists() and target.stat().st_size > 1000:
            continue
        if not download:
            return False
        try:
            log.info("downloading %s", url)
            urllib.request.urlretrieve(url, target)
        except Exception as exc:
            _state["error"] = f"model download failed: {exc}"
            return False
    return True


def available() -> bool:
    if not settings.enable_faces:
        return False
    try:
        import cv2
    except ImportError:
        return False
    return all((models_dir() / f).exists() for f, _ in MODELS.values())


def _load():
    if _state["det"] is not None or _state["error"]:
        return
    with _lock:
        if _state["det"] is not None or _state["error"]:
            return
        try:
            import cv2

            if not ensure_models():
                return
            _state["det"] = cv2.FaceDetectorYN.create(
                str(models_dir() / MODELS["detector"][0]), "", (320, 320), 0.85, 0.3, 50
            )
            _state["rec"] = cv2.FaceRecognizerSF.create(str(models_dir() / MODELS["recognizer"][0]), "")
        except Exception as exc:
            _state["error"] = str(exc)
            log.warning("face models unavailable: %s", exc)


def detect_and_embed(bgr: np.ndarray, max_faces: int = 6) -> list[dict]:
    if not settings.enable_faces:
        return []
    _load()
    det, rec = _state["det"], _state["rec"]
    if det is None:
        return []
    h, w = bgr.shape[:2]
    with _lock:
        det.setInputSize((w, h))
        _, faces = det.detect(bgr)
        out = []
        if faces is None:
            return out
        for f in sorted(faces, key=lambda r: -float(r[-1]))[:max_faces]:
            x, y, fw, fh = (int(v) for v in f[:4])
            if fw < MIN_FACE_PX or fh < MIN_FACE_PX:
                continue
            aligned = rec.alignCrop(bgr, f)
            emb = rec.feature(aligned).flatten().astype(np.float32)
            emb /= np.linalg.norm(emb) + 1e-9
            out.append({"bbox": [x, y, fw, fh], "score": round(float(f[-1]), 3), "emb": emb})
    return out


def cosine(a, b) -> float:
    a = np.asarray(a, dtype=np.float32)
    b = np.asarray(b, dtype=np.float32)
    return float(np.dot(a, b) / ((np.linalg.norm(a) * np.linalg.norm(b)) + 1e-9))


class Gallery:

    def __init__(self):
        self.items: dict[str, list[np.ndarray]] = {}
        self.sources: dict[str, list[str]] = {}

    def add(self, slug: str, emb: np.ndarray, source: str) -> None:
        self.items.setdefault(slug, []).append(np.asarray(emb, dtype=np.float32))
        self.sources.setdefault(slug, []).append(source)

    def match(self, emb) -> tuple[str, float] | None:
        best: tuple[str, float] | None = None
        for slug, embs in self.items.items():
            sim = max(cosine(emb, e) for e in embs)
            if sim >= MATCH_THRESHOLD and (best is None or sim > best[1]):
                best = (slug, round(sim, 3))
        return best

    def summary(self) -> dict[str, int]:
        return {k: len(v) for k, v in self.items.items()}


def load_curated_gallery(gallery: Gallery) -> None:
    import cv2

    root = settings.reference_dir / "faces"
    if not root.exists():
        return
    for person_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        for img_path in sorted(person_dir.glob("*")):
            if img_path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
                continue
            bgr = cv2.imdecode(np.fromfile(str(img_path), dtype=np.uint8), cv2.IMREAD_COLOR)
            if bgr is None:
                continue
            faces = detect_and_embed(bgr, max_faces=1)
            if faces:
                gallery.add(person_dir.name, faces[0]["emb"], f"reference/{person_dir.name}/{img_path.name}")
