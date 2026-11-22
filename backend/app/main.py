from __future__ import annotations

import logging
import mimetypes
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from .config import settings
from .service import Service

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(
    title="Kolekcjoner fejków API",
    version="0.1.0",
    description="Korelacja podejrzanych reklam w kampanie + lampki ryzyka AI / osoby publiczne / manipulacja.",
)
app.add_middleware(
    CORSMiddleware, allow_origins=list(settings.cors_origins), allow_methods=["*"], allow_headers=["*"]
)


@lru_cache(maxsize=1)
def svc() -> Service:
    return Service()


@app.on_event("startup")
def _startup() -> None:
    svc()


class ImportRequest(BaseModel):
    path: str | None = None


class LabelRequest(BaseModel):
    ai: bool | None = None


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/v1/status")
def status():
    return svc().status()


@app.post("/api/v1/dataset/import")
def import_dataset(body: ImportRequest | None = None):
    root = Path(body.path) if body and body.path else None
    if root is not None and not root.exists():
        raise HTTPException(404, f"folder {root} nie istnieje")
    return svc().import_dataset(root)


@app.post("/api/v1/dataset/upload")
async def upload_dataset(file: UploadFile = File(...)):
    if not (file.filename or "").lower().endswith(".zip"):
        raise HTTPException(415, "oczekiwano archiwum .zip")
    target = settings.raw_dir / Path(file.filename).name
    target.write_bytes(await file.read())
    return svc().import_dataset(zip_path=target)


@app.post("/api/v1/analyze")
async def analyze(
    files: list[UploadFile] | None = File(default=None),
    url: str | None = Form(default=None),
    label: str | None = Form(default=None),
):
    payload: list[tuple[str, bytes]] = []
    total = 0
    for f in files or []:
        data = await f.read()
        total += len(data)
        if total > settings.max_upload_mb * 1024 * 1024:
            raise HTTPException(413, f"pliki większe niż {settings.max_upload_mb} MB")
        payload.append((f.filename or "plik", data))
    url = (url or "").strip() or None
    if not payload and not url:
        raise HTTPException(422, "podaj plik(i) albo adres URL")
    mid = svc().create_upload(payload, url, label)
    return {"id": mid, "status": "pending"}


@app.get("/api/v1/materials")
def materials():
    return svc().material_list()


@app.get("/api/v1/materials/{mid}")
def material(mid: str):
    view = svc().material_view(mid)
    if not view:
        raise HTTPException(404, "nie ma takiego materiału")
    return view


@app.delete("/api/v1/materials/{mid}")
def delete_material(mid: str):
    if not svc().delete(mid):
        raise HTTPException(404, "nie ma takiego materiału")
    return {"deleted": mid}


@app.get("/api/v1/materials/{mid}/artifacts/{index}")
def artifact(mid: str, index: int):
    path = svc().artifact_path(mid, index)
    if not path:
        raise HTTPException(404, "nie ma takiego pliku")
    media_type = mimetypes.guess_type(path.replace("\\\\?\\", ""))[0] or "application/octet-stream"
    if media_type == "application/octet-stream":
        with open(path, "rb") as fh:
            head = fh.read(12)
        if head.startswith(b"\x89PNG"):
            media_type = "image/png"
        elif head.startswith(b"\xff\xd8"):
            media_type = "image/jpeg"
        elif head[:4] == b"RIFF":
            media_type = "image/webp"
    return FileResponse(path, media_type=media_type)


@app.post("/api/v1/materials/{mid}/label")
def label_material(mid: str, body: LabelRequest):
    if not svc().store.get(mid):
        raise HTTPException(404, "nie ma takiego materiału")
    if body.ai is not None:
        svc().store.set_label(mid, "ai", "true" if body.ai else "false")
    return svc().store.labels().get(mid, {})


@app.post("/api/v1/materials/{mid}/reprocess")
def reprocess(mid: str):
    if not svc().store.get(mid):
        raise HTTPException(404, "nie ma takiego materiału")
    svc().store.set_status(mid, "pending")
    svc().submit(mid)
    return {"id": mid, "status": "pending"}


@app.post("/api/v1/reprocess")
def reprocess_all():
    return {"queued": svc().reprocess_all()}


@app.get("/api/v1/campaigns")
def campaigns():
    return svc().campaigns()


@app.get("/api/v1/graph")
def graph(min_score: float = Query(0.15, ge=0, le=1)):
    return svc().graph(min_score)


@app.get("/api/v1/compare")
def compare(a: str, b: str):
    res = svc().compare(a, b)
    if res is None:
        raise HTTPException(404, "brak pary (materiał nieprzetworzony?)")
    return res


@app.post("/api/v1/ai/train")
def train_ai():
    return svc().train_ai()


@app.post("/api/v1/ai/seed")
def fetch_seed(shards: int = 10):
    return svc().fetch_seed(max(1, min(shards, 32)))


@app.get("/api/v1/export")
def export():
    return JSONResponse(
        svc().export(), headers={"Content-Disposition": 'attachment; filename="kolekcjoner-export.json"'}
    )
