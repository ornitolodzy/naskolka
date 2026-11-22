from __future__ import annotations

import hashlib
import json
import logging
import threading
from pathlib import Path

import numpy as np
from PIL import Image

from ..config import settings

log = logging.getLogger(__name__)
_lock = threading.Lock()
_engine = None
_failed = False


def available() -> bool:
    if not settings.enable_ocr:
        return False
    try:
        import rapidocr_onnxruntime
    except ImportError:
        return False
    return True


def _get_engine():
    global _engine, _failed
    if _engine is None and not _failed:
        with _lock:
            if _engine is None and not _failed:
                try:
                    from rapidocr_onnxruntime import RapidOCR

                    _engine = RapidOCR()
                except Exception as exc:
                    log.warning("OCR unavailable: %s", exc)
                    _failed = True
    return _engine


def _cache_path(key: str) -> Path:
    p = settings.cache_dir / "ocr"
    p.mkdir(parents=True, exist_ok=True)
    return p / f"{key}.json"


def ocr_image(img: Image.Image, cache_key: str | None = None) -> list[dict]:
    if not available():
        return []
    if cache_key is None:
        cache_key = hashlib.sha1(img.tobytes()[:2_000_000]).hexdigest()
    cp = _cache_path(cache_key)
    if cp.exists():
        try:
            return json.loads(cp.read_text("utf-8"))
        except ValueError:
            pass
    engine = _get_engine()
    if engine is None:
        return []
    scale = min(1.0, 1600 / max(img.width, img.height))
    work = img if scale >= 1 else img.resize((int(img.width * scale), int(img.height * scale)))
    arr = np.asarray(work.convert("RGB"))[:, :, ::-1]
    with _lock:
        result, _ = engine(arr)
    lines = []
    for box, text, score in result or []:
        xs = [p[0] / scale for p in box]
        ys = [p[1] / scale for p in box]
        lines.append(
            {
                "text": text,
                "score": round(float(score), 3),
                "box": [int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))],
            }
        )
    try:
        cp.write_text(json.dumps(lines, ensure_ascii=False), "utf-8")
    except OSError:
        pass
    return lines
