from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

ArtifactKind = Literal["har", "html", "mhtml", "screenshot", "page_image", "video", "meta", "other"]
MaterialSource = Literal["dataset", "upload", "url"]


@dataclass
class Artifact:
    path: str
    kind: ArtifactKind
    size: int
    name: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Material:
    id: str
    label: str
    source: MaterialSource
    root: str
    artifacts: list[Artifact] = field(default_factory=list)
    input_url: str | None = None


@dataclass
class Evidence:

    channel: str
    feature: str
    value: str
    weight: float
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
