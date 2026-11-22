from __future__ import annotations

import hashlib
import io
import re
from dataclasses import dataclass, field

import imagehash
import numpy as np
from PIL import Image, ImageFile

ImageFile.LOAD_TRUNCATED_IMAGES = True
Image.MAX_IMAGE_PIXELS = 80_000_000

_META_HINTS = {
    b"c2pa": "c2pa_manifest",
    b"jumb": "jumbf_box",
    b"trainedAlgorithmicMedia": "iptc_trained_algorithmic_media",
    b"compositeSynthetic": "iptc_composite_synthetic",
    b"compositeWithTrainedAlgorithmicMedia": "iptc_composite_with_ai",
    b"Midjourney": "generator_midjourney",
    b"DALL-E": "generator_dalle",
    b"DALL\xc2\xb7E": "generator_dalle",
    b"Stable Diffusion": "generator_stable_diffusion",
    b"stable-diffusion": "generator_stable_diffusion",
    b"ComfyUI": "generator_comfyui",
    b"Firefly": "generator_adobe_firefly",
    b"Imagen": "generator_imagen",
    b"SynthID": "synthid",
}


@dataclass
class ImageInfo:
    src: str
    kind: str
    width: int
    height: int
    sha1: str
    phash: str
    dhash: str
    meta_hints: list[str] = field(default_factory=list)
    software: str | None = None


def _hashes(img: Image.Image) -> tuple[str, str]:
    rgb = img.convert("RGB")
    return str(imagehash.phash(rgb)), str(imagehash.dhash(rgb))


def scan_meta_hints(data: bytes) -> list[str]:
    head = data[:600_000]
    return sorted({name for pat, name in _META_HINTS.items() if pat in head})


def load_image(path: str) -> tuple[Image.Image, bytes] | None:
    try:
        with open(path, "rb") as fh:
            data = fh.read()
        img = Image.open(io.BytesIO(data))
        img.load()
        if getattr(img, "is_animated", False):
            img.seek(0)
        return img, data
    except (OSError, ValueError, SyntaxError, Image.DecompressionBombError):
        return None


def image_info(path: str, src: str, kind: str) -> tuple[ImageInfo, Image.Image] | None:
    loaded = load_image(path)
    if loaded is None:
        return None
    img, data = loaded
    if img.width < 64 or img.height < 64:
        return None
    software = None
    try:
        exif = img.getexif()
        software = exif.get(0x0131) or None
        if isinstance(software, bytes):
            software = software.decode("utf-8", errors="replace")
    except Exception:
        software = None
    ph, dh = _hashes(img)
    info = ImageInfo(
        src=src,
        kind=kind,
        width=img.width,
        height=img.height,
        sha1=hashlib.sha1(data).hexdigest(),
        phash=ph,
        dhash=dh,
        meta_hints=scan_meta_hints(data),
        software=str(software)[:80] if software else None,
    )
    return info, img.convert("RGB")


def frame_to_image(frame_bgr: np.ndarray) -> Image.Image:
    return Image.fromarray(frame_bgr[:, :, ::-1])


def video_frames(path: str, n: int) -> tuple[list[tuple[float, np.ndarray]], dict]:
    try:
        import cv2
    except ImportError:
        return [], {"error": "opencv not installed"}
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        return [], {"error": "cannot open video"}
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0) or 25.0
    meta = {
        "frames": total,
        "fps": round(fps, 2),
        "duration_s": round(total / fps, 1) if total else None,
        "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0),
        "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0),
    }
    frames: list[tuple[float, np.ndarray]] = []
    if total <= 0:
        cap.release()
        return frames, meta
    idxs = sorted({int(total * (i + 0.5) / n) for i in range(n)})
    for idx in idxs:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ok, frame = cap.read()
        if ok and frame is not None:
            h, w = frame.shape[:2]
            scale = 1280 / max(h, w)
            if scale < 1:
                frame = cv2.resize(frame, (int(w * scale), int(h * scale)))
            frames.append((round(idx / fps, 2), frame))
    cap.release()
    return frames, meta


_HEX = re.compile(r"^[0-9a-f]+$")


def hamming(a: str, b: str) -> int:
    if not a or not b or len(a) != len(b) or not _HEX.match(a) or not _HEX.match(b):
        return 64
    return bin(int(a, 16) ^ int(b, 16)).count("1")
