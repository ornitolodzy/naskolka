from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _float(name: str, default: float) -> float:
    raw = os.getenv(name)
    return float(raw) if raw else default


BACKEND_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_ROOT.parent


@dataclass(frozen=True)
class Settings:
    data_dir: Path = field(default_factory=lambda: Path(os.getenv("FK_DATA_DIR", PROJECT_ROOT / "data")))
    reference_dir: Path = field(
        default_factory=lambda: Path(os.getenv("FK_REFERENCE_DIR", BACKEND_ROOT / "reference"))
    )

    enable_ocr: bool = field(default_factory=lambda: _bool("FK_ENABLE_OCR", True))
    enable_faces: bool = field(default_factory=lambda: _bool("FK_ENABLE_FACES", True))
    enable_online: bool = field(default_factory=lambda: _bool("FK_ENABLE_ONLINE", False))
    enable_asr: bool = field(default_factory=lambda: _bool("FK_ENABLE_ASR", True))
    asr_model: str = field(default_factory=lambda: os.getenv("FK_ASR_MODEL", "small"))
    asr_device: str = field(default_factory=lambda: os.getenv("FK_ASR_DEVICE", "auto"))
    enable_clip: bool = field(default_factory=lambda: _bool("FK_ENABLE_CLIP", True))
    clip_model: str = field(default_factory=lambda: os.getenv("FK_CLIP_MODEL", "l14"))
    video_frames: int = field(default_factory=lambda: int(os.getenv("FK_VIDEO_FRAMES", "12")))
    max_upload_mb: int = field(default_factory=lambda: int(os.getenv("FK_MAX_UPLOAD_MB", "600")))

    ollama_url: str = field(default_factory=lambda: os.getenv("FK_OLLAMA_URL", ""))
    ollama_model: str = field(
        default_factory=lambda: os.getenv("FK_OLLAMA_MODEL", "SpeakLeash/bielik-11b-v2.3-instruct:Q4_K_M")
    )

    link_threshold: float = field(default_factory=lambda: _float("FK_LINK_THRESHOLD", 0.30))
    assign_threshold: float = field(default_factory=lambda: _float("FK_ASSIGN_THRESHOLD", 0.30))

    cors_origins: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            o.strip() for o in os.getenv("FK_CORS_ORIGINS", "http://localhost:4200").split(",") if o.strip()
        )
    )

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def cache_dir(self) -> Path:
        return self.data_dir / "cache"

    @property
    def models_dir(self) -> Path:
        return self.data_dir / "models"

    @property
    def seed_dir(self) -> Path:
        return self.data_dir / "ai_seed"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "kolekcjoner.sqlite3"


settings = Settings()
