from __future__ import annotations

import io
import json
import logging
import math
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from ..config import settings

log = logging.getLogger(__name__)
MODEL_NAME = "pu-clip-spectral-v2"
MIN_POSITIVES = 3
MIN_OTHERS = 3
RELIABLE_POSITIVES = 20
RELIABLE_SOURCES = 3
RELIABLE_AUC = 0.80
SUPERVISED_MIN_NEGATIVES = 20
FLAG_THRESHOLD = 0.60
MAX_UNLABELED_FLAG_RATE = 0.35
WEB_MAX_SIDE = 1024
WEB_JPEG_QUALITY = 85


def mask_boxes(img: Image.Image, boxes: list[list[int]]) -> Image.Image:
    if not boxes:
        return img
    out = img.copy()
    draw = ImageDraw.Draw(out)
    for x0, y0, x1, y1 in boxes:
        pad = 6
        draw.rectangle([x0 - pad, y0 - pad, x1 + pad, y1 + pad], fill=(127, 127, 127))
    return out


def webify(img: Image.Image) -> Image.Image:
    im = img.convert("RGB")
    if max(im.size) > WEB_MAX_SIDE:
        im.thumbnail((WEB_MAX_SIDE, WEB_MAX_SIDE), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=WEB_JPEG_QUALITY)
    buf.seek(0)
    return Image.open(buf).convert("RGB")


def image_vector(img: Image.Image) -> list[float]:
    g = img.convert("L")
    side = 256
    scale = side / min(g.size)
    g = g.resize((max(side, int(g.width * scale)), max(side, int(g.height * scale))))
    left, top = (g.width - side) // 2, (g.height - side) // 2
    g = g.crop((left, top, left + side, top + side))
    a = np.asarray(g, dtype=np.float32) / 255.0

    spec = np.log1p(np.abs(np.fft.fftshift(np.fft.fft2(a - a.mean()))))
    yy, xx = np.indices(spec.shape)
    r = np.hypot(yy - side / 2, xx - side / 2).astype(int)
    radial = np.bincount(r.ravel(), spec.ravel()) / np.maximum(np.bincount(r.ravel()), 1)
    radial = radial[: side // 2]
    bins = np.array_split(radial, 16)
    prof = np.array([b.mean() for b in bins])
    prof = (prof - prof.mean()) / (prof.std() + 1e-6)
    hf_ratio = float(radial[side // 4 :].mean() / (radial[: side // 8].mean() + 1e-6))

    med = np.asarray(g.filter(ImageFilter.MedianFilter(3)), dtype=np.float32) / 255.0
    resid = a - med
    r_std = float(resid.std())
    r_kurt = float(((resid - resid.mean()) ** 4).mean() / (resid.var() ** 2 + 1e-9))
    lap = a[1:-1, 1:-1] * 4 - a[:-2, 1:-1] - a[2:, 1:-1] - a[1:-1, :-2] - a[1:-1, 2:]
    lap_var = float(lap.var())

    hsv = np.asarray(img.convert("HSV").resize((128, 128)), dtype=np.float32) / 255.0
    sat_mean, sat_std = float(hsv[..., 1].mean()), float(hsv[..., 1].std())
    val_std = float(hsv[..., 2].std())

    vec = list(prof) + [
        hf_ratio,
        math.log(r_std + 1e-6),
        math.log(r_kurt + 1e-6),
        math.log(lap_var + 1e-9),
        sat_mean,
        sat_std,
        val_std,
    ]
    return [round(float(v), 5) for v in vec]


def _model_path() -> Path:
    p = settings.data_dir / "models"
    p.mkdir(parents=True, exist_ok=True)
    return p / "ai_head.json"


class AIDetector:
    def __init__(self):
        self.model: dict | None = None
        self.load()

    def load(self) -> None:
        try:
            self.model = json.loads(_model_path().read_text("utf-8"))
        except (OSError, ValueError):
            self.model = None

    @property
    def trained(self) -> bool:
        return self.model is not None

    @property
    def reliable(self) -> bool:
        if not self.model or self.model.get("model") != MODEL_NAME:
            return False
        auc = self.model.get("heldout_auc")
        flag_rate = self.model.get("unlabeled_flag_rate")
        return (
            self.model.get("positives", 0) >= RELIABLE_POSITIVES
            and self.model.get("positive_sources", 0) >= RELIABLE_SOURCES
            and auc is not None
            and auc >= RELIABLE_AUC
            and (flag_rate is None or flag_rate <= MAX_UNLABELED_FLAG_RATE)
        )

    def info(self) -> dict:
        requires = {"positives": RELIABLE_POSITIVES, "positive_sources": RELIABLE_SOURCES, "heldout_auc": RELIABLE_AUC,
                    "max_unlabeled_flag_rate": MAX_UNLABELED_FLAG_RATE}
        if not self.model:
            return {"trained": False, "reliable": False, "model": MODEL_NAME, "reliable_requires": requires}
        return {k: v for k, v in self.model.items() if k not in {"coef", "mean", "std"}} | {
            "trained": True,
            "reliable": self.reliable,
            "reliable_requires": requires,
        }

    def _matrix(self, entries: list[dict], clip_model: str | None) -> tuple[np.ndarray, list[int]]:
        rows, keep = [], []
        for i, e in enumerate(entries):
            if clip_model:
                if "c" not in e or e.get("cm") != clip_model:
                    continue
                rows.append(list(e["v"]) + list(e["c"]))
            else:
                rows.append(list(e["v"]))
            keep.append(i)
        return np.asarray(rows, dtype=np.float64), keep

    def score_images(self, vectors: list[dict]) -> list[tuple[str, float]]:
        if not self.model or not vectors or self.model.get("model") != MODEL_NAME:
            return []
        X, keep = self._matrix(vectors, self.model.get("clip_model"))
        if not keep or X.shape[1] != len(self.model["mean"]):
            return []
        Xn = (X - np.asarray(self.model["mean"])) / np.asarray(self.model["std"])
        z = Xn @ np.asarray(self.model["coef"]) + self.model["intercept"]
        p = np.clip((1 / (1 + np.exp(-z))) / self.model["c"], 0, 1)
        return [(vectors[i].get("src", ""), round(float(pi), 3)) for i, pi in zip(keep, p)]

    def score_vectors(self, vectors: list[dict]) -> float | None:
        scored = self.score_images(vectors)
        if not scored:
            return None
        top = sorted(p for _, p in scored)[-3:]
        return round(float(np.mean(top)), 3)

    def train(self, samples: list[tuple[dict, str, str]]) -> dict:
        from sklearn.linear_model import LogisticRegression
        from sklearn.metrics import roc_auc_score
        from sklearn.model_selection import GroupKFold, StratifiedKFold, cross_val_predict

        cms = Counter(e.get("cm") for e, _, _ in samples if "c" in e)
        clip_model, with_clip = cms.most_common(1)[0] if cms else (None, 0)
        use_clip = with_clip >= 0.9 * len(samples) and with_clip > 0
        if use_clip:
            samples = [s for s in samples if "c" in s[0] and s[0].get("cm") == clip_model]
        else:
            clip_model = None

        unlabeled = [e for e, l, _ in samples if l == "unl"]
        n_unl = len(unlabeled)
        n_neg = sum(1 for _, l, _ in samples if l == "neg")
        mode = "supervised" if n_neg >= SUPERVISED_MIN_NEGATIVES else "pu"
        if mode == "supervised":
            samples = [x for x in samples if x[1] != "unl"]

        labels = np.asarray([l for _, l, _ in samples])
        rng = np.random.default_rng(0)
        groups = np.asarray([g if l == "pos" else f"other-{rng.integers(5)}" for _, l, g in samples])
        n_pos = int((labels == "pos").sum())
        n_other = len(samples) - n_pos
        pos_sources = sorted({g for _, l, g in samples if l == "pos"})
        if n_pos < MIN_POSITIVES or n_other < MIN_OTHERS:
            return {
                "trained": False,
                "reason": f"za mało przykładów: {n_pos} pozytywnych (min {MIN_POSITIVES}), "
                f"{n_other} pozostałych (min {MIN_OTHERS})",
                "positives": n_pos,
                "others": n_other,
            }

        X, _ = self._matrix([e for e, _, _ in samples], clip_model)
        s = (labels == "pos").astype(int)
        mean, std = X.mean(0), X.std(0) + 1e-6
        Xn = (X - mean) / std
        C = 0.05 if use_clip else 0.5
        clf = LogisticRegression(C=C, class_weight="balanced", max_iter=4000)
        folds = max(2, min(5, n_pos, n_other))
        p_cv = cross_val_predict(clf, Xn, s, cv=StratifiedKFold(folds, shuffle=True, random_state=0),
                                 method="predict_proba")[:, 1]
        c = float(np.clip(p_cv[s == 1].mean(), 0.05, 1.0)) if mode == "pu" else 1.0

        heldout_auc = None
        labeled = labels != "unl"
        if n_neg >= 5 and len(pos_sources) >= 3:
            k = min(5, len(set(groups)))
            p_ho = np.full(len(s), np.nan)
            for tr, te in GroupKFold(n_splits=k).split(Xn, s, groups):
                if s[tr].sum() == 0 or s[tr].sum() == len(tr):
                    continue
                m = LogisticRegression(C=C, class_weight="balanced", max_iter=4000).fit(Xn[tr], s[tr])
                p_ho[te] = m.predict_proba(Xn[te])[:, 1]
            mask = labeled & ~np.isnan(p_ho)
            if len(set(s[mask])) == 2:
                heldout_auc = round(float(roc_auc_score(s[mask], p_ho[mask])), 3)

        clf.fit(Xn, s)
        self.model = {
            "model": MODEL_NAME,
            "mode": mode,
            "clip_model": clip_model,
            "features": f"clip-{clip_model} + spectral" if clip_model else "spectral",
            "coef": clf.coef_[0].tolist(),
            "intercept": float(clf.intercept_[0]),
            "mean": mean.tolist(),
            "std": std.tolist(),
            "c": c,
            "positives": n_pos,
            "positive_sources": len(pos_sources),
            "negatives": n_neg,
            "unlabeled": n_unl,
            "heldout_auc": heldout_auc,
            "cv_mean_p_pos": round(float(p_cv[s == 1].mean()), 3),
            "cv_mean_p_other": round(float(p_cv[s == 0].mean()), 3),
        }
        scored = self.score_images(unlabeled)
        self.model["unlabeled_flag_rate"] = (
            round(float(np.mean([p >= FLAG_THRESHOLD for _, p in scored])), 3) if scored else None
        )
        _model_path().write_text(json.dumps(self.model), "utf-8")
        return self.info()


detector = AIDetector()
