from __future__ import annotations

import io
import json
import logging
import re
from pathlib import Path

from PIL import Image

from .config import settings
from .features import ai_detector, clip

log = logging.getLogger(__name__)
OPENFAKE_REPO = "ComplexDataLab/OpenFake"
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9.+-]+", "-", s.lower()).strip("-") or "unknown"


def fetch_openfake(shards: int = 3, max_per_source: int = 40, max_per_real_source: int = 250) -> dict:
    import pyarrow.parquet as pq
    from huggingface_hub import HfApi, hf_hub_download

    info = HfApi().dataset_info(OPENFAKE_REPO, files_metadata=True)
    small = sorted(
        (s.rfilename for s in info.siblings
         if s.rfilename.startswith("core/train-") and s.rfilename.endswith(".parquet") and (s.size or 0) < 300_000_000),
    )[:shards]
    counts: dict[str, int] = {}
    cache = settings.cache_dir / "openfake"
    for name in small:
        path = hf_hub_download(OPENFAKE_REPO, name, repo_type="dataset", local_dir=str(cache))
        table = pq.read_table(path, columns=["image", "label", "model", "row_id"])
        for row in table.to_pylist():
            label = "ai" if row["label"] == "fake" else "real"
            source = _slug(row["model"] or "unknown")
            key = f"{label}/{source}"
            cap = max_per_source if label == "ai" else max_per_real_source
            if counts.get(key, 0) >= cap or not (row.get("image") or {}).get("bytes"):
                continue
            data = row["image"]["bytes"]
            try:
                fmt = (Image.open(io.BytesIO(data)).format or "png").lower()
            except Exception:
                continue
            ext = ".jpg" if fmt == "jpeg" else f".{fmt}"
            target = settings.seed_dir / label / source / f"{_slug(row['row_id'] or str(counts.get(key, 0)))}{ext}"
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                target.write_bytes(data)
            counts[key] = counts.get(key, 0) + 1
        Path(path).unlink(missing_ok=True)
    (settings.seed_dir / "SOURCE.txt").write_text(
        f"{OPENFAKE_REPO} (CC-BY-NC-4.0), shards: {', '.join(small)}\n", "utf-8")
    return {"shards": small, "ai": sum(v for k, v in counts.items() if k.startswith("ai/")),
            "real": sum(v for k, v in counts.items() if k.startswith("real/")),
            "sources": len(counts)}


def seed_files() -> list[tuple[Path, str, str]]:
    out = []
    for label, tag in (("ai", "pos"), ("real", "neg")):
        root = settings.seed_dir / label
        if not root.is_dir():
            continue
        for src_dir in sorted(p for p in root.iterdir() if p.is_dir()):
            for f in sorted(src_dir.iterdir()):
                if f.suffix.lower() in IMAGE_EXT:
                    out.append((f, tag, f"seed:{label}/{src_dir.name}"))
    return out


def summary() -> dict:
    files = seed_files()
    return {
        "ai": sum(1 for _, t, _ in files if t == "pos"),
        "real": sum(1 for _, t, _ in files if t == "neg"),
        "ai_sources": len({s for _, t, s in files if t == "pos"}),
        "real_sources": len({s for _, t, s in files if t == "neg"}),
    }


def load_samples() -> list[tuple[dict, str, str]]:
    files = seed_files()
    if not files:
        return []
    cache_path = settings.cache_dir / "seed_vectors.json"
    try:
        cache = json.loads(cache_path.read_text("utf-8"))
    except (OSError, ValueError):
        cache = {}
    use_clip = settings.enable_clip
    cm = clip.model_key()
    samples, changed = [], False
    for f, tag, source in files:
        key = f"{f.relative_to(settings.seed_dir).as_posix()}:{f.stat().st_size}"
        entry = cache.get(key)
        if entry is None or (use_clip and entry.get("cm") != cm):
            try:
                with Image.open(f) as raw:
                    img = ai_detector.webify(raw)
            except Exception:
                continue
            entry = {"src": key, "kind": "seed", "v": ai_detector.image_vector(img)}
            if use_clip and (emb := clip.embed(img)):
                entry["c"] = emb
                entry["cm"] = cm
            cache[key] = entry
            changed = True
        samples.append((entry, tag, source))
    if changed:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(cache), "utf-8")
    return samples
