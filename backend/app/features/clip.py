from __future__ import annotations

import logging
import threading

import numpy as np
from PIL import Image

from ..config import settings

log = logging.getLogger(__name__)
MODELS = {
    "b32": ("Xenova/clip-vit-base-patch32", "onnx/vision_model_quantized.onnx"),
    "l14": ("Xenova/clip-vit-large-patch14", "onnx/vision_model_quantized.onnx"),
}
SIZE = 224
MEAN = np.array([0.48145466, 0.4578275, 0.40821073], dtype=np.float32)
STD = np.array([0.26862954, 0.26130258, 0.27577711], dtype=np.float32)

_lock = threading.Lock()
_state: dict = {"session": None, "error": None}


def model_key() -> str:
    return settings.clip_model if settings.clip_model in MODELS else "l14"


def _local_dir():
    return settings.models_dir / "clip" / model_key()


def model_path():
    return _local_dir() / MODELS[model_key()][1]


def ensure_model(download: bool = True) -> bool:
    if model_path().exists():
        return True
    if not download:
        return False
    try:
        from huggingface_hub import hf_hub_download

        repo, file = MODELS[model_key()]
        hf_hub_download(repo, file, local_dir=str(_local_dir()))
        return True
    except Exception as exc:
        _state["error"] = f"nie udało się pobrać modelu CLIP: {exc}"
        log.warning(_state["error"])
        return False


def _session():
    with _lock:
        if _state["session"] is None and _state["error"] is None:
            if not ensure_model():
                return None
            try:
                import onnxruntime as ort

                _state["session"] = ort.InferenceSession(str(model_path()), providers=["CPUExecutionProvider"])
            except Exception as exc:
                _state["error"] = f"nie udało się załadować CLIP: {exc}"
                log.warning(_state["error"])
        return _state["session"]


def available() -> bool:
    return settings.enable_clip and _state["error"] is None and (_state["session"] is not None or model_path().exists())


def info() -> dict:
    return {"enabled": settings.enable_clip, "model": MODELS[model_key()][0], "key": model_key(),
            "present": model_path().exists(), "error": _state["error"]}


def _preprocess(img: Image.Image) -> np.ndarray:
    im = img.convert("RGB")
    scale = SIZE / min(im.size)
    im = im.resize((max(SIZE, round(im.width * scale)), max(SIZE, round(im.height * scale))), Image.BICUBIC)
    left, top = (im.width - SIZE) // 2, (im.height - SIZE) // 2
    im = im.crop((left, top, left + SIZE, top + SIZE))
    arr = (np.asarray(im, dtype=np.float32) / 255.0 - MEAN) / STD
    return arr.transpose(2, 0, 1)[None]


def embed(img: Image.Image) -> list[float] | None:
    if not settings.enable_clip:
        return None
    sess = _session()
    if sess is None:
        return None
    out = sess.run(None, {"pixel_values": _preprocess(img)})[0][0]
    out = out / (np.linalg.norm(out) + 1e-9)
    return [round(float(x), 4) for x in out]
