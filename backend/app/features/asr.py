from __future__ import annotations

import hashlib
import importlib.util
import json
import logging
import os
import threading

import numpy as np

from ..config import settings

log = logging.getLogger(__name__)
SAMPLE_RATE = 16000

_lock = threading.Lock()
_state: dict = {"model": None, "device": None, "error": None}


def _device() -> str:
    if settings.asr_device != "auto":
        return settings.asr_device
    try:
        import ctranslate2

        return "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
    except Exception:
        return "cpu"


def installed() -> bool:
    return importlib.util.find_spec("faster_whisper") is not None


def available() -> bool:
    return settings.enable_asr and installed() and _state["error"] is None


def info() -> dict:
    return {
        "enabled": settings.enable_asr,
        "installed": installed(),
        "model": settings.asr_model,
        "device": _state["device"] or _device(),
        "loaded": _state["model"] is not None,
        "error": _state["error"],
    }


def _model():
    with _lock:
        if _state["model"] is None and _state["error"] is None:
            try:
                from faster_whisper import WhisperModel

                dev = _device()
                _state["model"] = WhisperModel(
                    settings.asr_model,
                    device=dev,
                    compute_type="float16" if dev == "cuda" else "int8",
                    download_root=str(settings.models_dir / "whisper"),
                )
                _state["device"] = dev
            except Exception as exc:
                _state["error"] = f"nie udało się załadować Whisper: {exc}"
                log.warning(_state["error"])
        return _state["model"]


def decode_audio(path: str) -> np.ndarray | None:
    import av

    with open(path, "rb") as fh, av.open(fh) as container:
        if not container.streams.audio:
            return None
        resampler = av.AudioResampler(format="s16", layout="mono", rate=SAMPLE_RATE)
        chunks = []
        for frame in container.decode(audio=0):
            chunks.extend(r.to_ndarray().reshape(-1) for r in resampler.resample(frame))
        chunks.extend(r.to_ndarray().reshape(-1) for r in resampler.resample(None))
    if not chunks:
        return None
    return np.concatenate(chunks).astype(np.float32) / 32768.0


def _cache_key(path: str) -> str:
    h = hashlib.sha1()
    size = os.path.getsize(path)
    h.update(str(size).encode())
    with open(path, "rb") as fh:
        h.update(fh.read(1 << 20))
        if size > 2 << 20:
            fh.seek(-(1 << 20), os.SEEK_END)
            h.update(fh.read())
    return f"{h.hexdigest()}-{settings.asr_model}"


def transcribe(path: str) -> dict | None:
    cache = settings.cache_dir / "asr"
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / f"{_cache_key(path)}.json"
    if target.exists():
        return json.loads(target.read_text("utf-8"))

    audio = decode_audio(path)
    if audio is None or len(audio) < SAMPLE_RATE // 2:
        result = {"language": None, "duration": 0.0, "text": "", "segments": [], "no_audio": True}
    else:
        model = _model()
        if model is None:
            return None
        segments, meta = model.transcribe(audio, vad_filter=True, beam_size=1)
        segs = [{"start": round(s.start, 1), "end": round(s.end, 1), "text": s.text.strip()} for s in segments]
        result = {
            "language": meta.language,
            "language_probability": round(float(meta.language_probability), 2),
            "duration": round(float(meta.duration), 1),
            "text": " ".join(s["text"] for s in segs if s["text"]),
            "segments": segs,
        }
    result["model"] = settings.asr_model
    target.write_text(json.dumps(result, ensure_ascii=False), "utf-8")
    return result
