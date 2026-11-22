from __future__ import annotations

import json
import logging
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from ..config import settings

log = logging.getLogger(__name__)
MODEL_NAME = "pu-spectral-v1"
MIN_POSITIVES = 3
MIN_OTHERS = 3
RELIABLE_POSITIVES = 20
RELIABLE_MATERIALS = 3


def mask_boxes(img: Image.Image, boxes: list[list[int]]) -> Image.Image:
    if not boxes:
        return img
    out = img.copy()
    draw = ImageDraw.Draw(out)
    for x0, y0, x1, y1 in boxes:
        pad = 6
        draw.rectangle([x0 - pad, y0 - pad, x1 + pad, y1 + pad], fill=(127, 127, 127))
    return out


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
        return bool(
            self.model
            and self.model.get("positives", 0) >= RELIABLE_POSITIVES
            and self.model.get("positive_materials", 0) >= RELIABLE_MATERIALS
        )

    def info(self) -> dict:
        if not self.model:
            return {"trained": False, "reliable": False, "model": MODEL_NAME, "min_positives": MIN_POSITIVES}
        return {k: v for k, v in self.model.items() if k not in {"coef", "mean", "std"}} | {
            "trained": True,
            "reliable": self.reliable,
            "reliable_requires": {"positives": RELIABLE_POSITIVES, "positive_materials": RELIABLE_MATERIALS},
        }

    def score_vectors(self, vectors: list[dict]) -> float | None:
        if not self.model or not vectors:
            return None
        X = (np.asarray([v["v"] for v in vectors]) - np.asarray(self.model["mean"])) / np.asarray(self.model["std"])
        z = X @ np.asarray(self.model["coef"]) + self.model["intercept"]
        p_labeled = 1 / (1 + np.exp(-z))
        p = np.clip(p_labeled / self.model["c"], 0, 1)
        top = np.sort(p)[-3:]
        return round(float(top.mean()), 3)

    def train(self, samples: list[tuple[list[float], str, str]]) -> dict:
        from sklearn.linear_model import LogisticRegression
        from sklearn.model_selection import StratifiedKFold, cross_val_predict

        pos = [v for v, l, _ in samples if l == "pos"]
        other = [v for v, l, _ in samples if l != "pos"]
        n_neg = sum(1 for _, l, _ in samples if l == "neg")
        pos_materials = len({m for _, l, m in samples if l == "pos"})
        if len(pos) < MIN_POSITIVES or len(other) < MIN_OTHERS:
            return {
                "trained": False,
                "reason": f"za mało przykładów: {len(pos)} pozytywnych (min {MIN_POSITIVES}), "
                f"{len(other)} pozostałych (min {MIN_OTHERS})",
                "positives": len(pos),
                "others": len(other),
            }
        X = np.asarray(pos + other, dtype=np.float64)
        s = np.asarray([1] * len(pos) + [0] * len(other))
        mean, std = X.mean(0), X.std(0) + 1e-6
        Xn = (X - mean) / std
        clf = LogisticRegression(C=0.5, class_weight="balanced", max_iter=2000)
        folds = max(2, min(5, len(pos), len(other)))
        p_cv = cross_val_predict(clf, Xn, s, cv=StratifiedKFold(folds, shuffle=True, random_state=0), method="predict_proba")[:, 1]
        c = float(np.clip(p_cv[s == 1].mean(), 0.05, 1.0))
        clf.fit(Xn, s)
        self.model = {
            "model": MODEL_NAME,
            "coef": clf.coef_[0].tolist(),
            "intercept": float(clf.intercept_[0]),
            "mean": mean.tolist(),
            "std": std.tolist(),
            "c": c,
            "positives": len(pos),
            "positive_materials": pos_materials,
            "negatives": n_neg,
            "unlabeled": len(other) - n_neg,
            "cv_mean_p_pos": round(float(p_cv[s == 1].mean()), 3),
            "cv_mean_p_other": round(float(p_cv[s == 0].mean()), 3),
        }
        _model_path().write_text(json.dumps(self.model), "utf-8")
        return self.info()


detector = AIDetector()
