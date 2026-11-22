from __future__ import annotations

import os
import re
from pathlib import Path

from ..models import Artifact, ArtifactKind

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".avif"}
VIDEO_EXT = {".mp4", ".mov", ".webm", ".mkv", ".avi", ".m4v"}
HTML_EXT = {".html", ".htm"}

_ASSET_DIR = re.compile(r"(_files|_pliki|[\\/]resources)([\\/]|$)", re.IGNORECASE)
_MIN_PAGE_IMAGE_BYTES = 6_000


def long_path(p: str | Path) -> str:
    s = str(Path(p).resolve())
    if os.name == "nt" and not s.startswith("\\\\?\\"):
        return "\\\\?\\" + s
    return s


def _sniff_image(path: str) -> bool:
    try:
        with open(path, "rb") as fh:
            head = fh.read(16)
    except OSError:
        return False
    return (
        head.startswith(b"\x89PNG")
        or head.startswith(b"\xff\xd8\xff")
        or head.startswith(b"GIF8")
        or (head[:4] == b"RIFF" and head[8:12] == b"WEBP")
    )


def classify(path: str, rel: str) -> ArtifactKind | None:
    name = os.path.basename(path).lower()
    ext = os.path.splitext(name)[1]
    in_assets = bool(_ASSET_DIR.search(rel))

    if ext == ".har":
        return "har"
    if ext in {".mhtml", ".mht"}:
        return "mhtml"
    if ext in VIDEO_EXT:
        return "video"
    if name.endswith(".info.json") or name == "manifest.json":
        return "meta"
    if ext in HTML_EXT:
        if in_assets and name not in {"dom.html"}:
            return "html" if name.startswith("index") else None
        return "html"
    if ext in IMAGE_EXT or (in_assets and ext in {"", ".pobrane"} and _sniff_image(path)):
        size = os.path.getsize(path)
        if in_assets:
            return "page_image" if size >= _MIN_PAGE_IMAGE_BYTES else None
        return "screenshot"
    return None


def collect_artifacts(root: str | Path) -> list[Artifact]:
    root_lp = long_path(root)
    out: list[Artifact] = []
    for dirpath, _dirs, files in os.walk(root_lp):
        for fname in sorted(files):
            full = os.path.join(dirpath, fname)
            rel = os.path.relpath(full, root_lp)
            kind = classify(full, rel)
            if kind is None:
                continue
            out.append(Artifact(path=full, kind=kind, size=os.path.getsize(full), name=rel.replace("\\", "/")))
    order = {"meta": 0, "har": 1, "html": 2, "mhtml": 3, "screenshot": 4, "video": 5, "page_image": 6}
    out.sort(key=lambda a: (order.get(a.kind, 9), a.name))
    return out
