from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from .ingest.collect import long_path
from .models import Artifact, Material

_SCHEMA = """
CREATE TABLE IF NOT EXISTS materials (
    id          TEXT PRIMARY KEY,
    label       TEXT NOT NULL,
    source      TEXT NOT NULL,
    root        TEXT NOT NULL,
    input_url   TEXT,
    artifacts   TEXT NOT NULL,
    features    TEXT,
    status      TEXT NOT NULL DEFAULT 'pending',
    error       TEXT,
    created_at  REAL NOT NULL,
    updated_at  REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS labels (
    material_id TEXT NOT NULL,
    key         TEXT NOT NULL,
    value       TEXT NOT NULL,
    created_at  REAL NOT NULL,
    PRIMARY KEY (material_id, key)
);
"""


REL_PREFIX = "@data/"


class Store:

    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._base = db_path.parent.resolve()
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self.version = 0
        self._relativize_existing()

    def _to_stored(self, path: str) -> str:
        plain = path[4:] if path.startswith("\\\\?\\") else path
        try:
            rel = Path(plain).resolve().relative_to(self._base)
        except (ValueError, OSError):
            return path
        return REL_PREFIX + rel.as_posix()

    def _from_stored(self, path: str) -> str:
        if path.startswith(REL_PREFIX):
            return long_path(self._base / path[len(REL_PREFIX):])
        return path

    def _relativize_existing(self) -> None:
        with self._lock:
            rows = self._conn.execute("SELECT id, root, artifacts FROM materials").fetchall()
            for r in rows:
                arts = json.loads(r["artifacts"])
                for a in arts:
                    a["path"] = self._to_stored(a["path"])
                root = self._to_stored(r["root"])
                new_arts = json.dumps(arts, ensure_ascii=False)
                if root != r["root"] or new_arts != r["artifacts"]:
                    self._conn.execute("UPDATE materials SET root=?, artifacts=? WHERE id=?", (root, new_arts, r["id"]))
            self._conn.commit()

    def _bump(self) -> None:
        self.version += 1

    def touch(self) -> None:
        self._bump()

    def upsert_material(self, m: Material, status: str = "pending") -> None:
        now = time.time()
        with self._lock:
            self._conn.execute(
                """INSERT INTO materials (id, label, source, root, input_url, artifacts, status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET label=excluded.label, root=excluded.root,
                     input_url=excluded.input_url, artifacts=excluded.artifacts, status=excluded.status,
                     updated_at=excluded.updated_at""",
                (
                    m.id,
                    m.label,
                    m.source,
                    self._to_stored(m.root),
                    m.input_url,
                    json.dumps([{**a.to_dict(), "path": self._to_stored(a.path)} for a in m.artifacts], ensure_ascii=False),
                    status,
                    now,
                    now,
                ),
            )
            self._conn.commit()
            self._bump()

    def save_features(self, material_id: str, features: dict[str, Any], status: str = "done", error: str | None = None) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE materials SET features=?, status=?, error=?, updated_at=? WHERE id=?",
                (json.dumps(features, ensure_ascii=False), status, error, time.time(), material_id),
            )
            self._conn.commit()
            self._bump()

    def set_status(self, material_id: str, status: str, error: str | None = None) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE materials SET status=?, error=?, updated_at=? WHERE id=?",
                (status, error, time.time(), material_id),
            )
            self._conn.commit()
            self._bump()

    def delete(self, material_id: str) -> bool:
        with self._lock:
            cur = self._conn.execute("DELETE FROM materials WHERE id=?", (material_id,))
            self._conn.execute("DELETE FROM labels WHERE material_id=?", (material_id,))
            self._conn.commit()
            self._bump()
            return cur.rowcount > 0

    def get(self, material_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM materials WHERE id=?", (material_id,)).fetchone()
        return self._row(row) if row else None

    def all(self, with_features: bool = True) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM materials ORDER BY created_at").fetchall()
        return [self._row(r, with_features) for r in rows]

    def material(self, material_id: str) -> Material | None:
        row = self.get(material_id)
        if not row:
            return None
        return Material(
            id=row["id"],
            label=row["label"],
            source=row["source"],
            root=row["root"],
            input_url=row["input_url"],
            artifacts=[Artifact(**a) for a in row["artifacts"]],
        )

    def set_label(self, material_id: str, key: str, value: str) -> None:
        with self._lock:
            self._conn.execute(
                """INSERT INTO labels (material_id, key, value, created_at) VALUES (?, ?, ?, ?)
                   ON CONFLICT(material_id, key) DO UPDATE SET value=excluded.value, created_at=excluded.created_at""",
                (material_id, key, value, time.time()),
            )
            self._conn.commit()
            self._bump()

    def labels(self) -> dict[str, dict[str, str]]:
        with self._lock:
            rows = self._conn.execute("SELECT material_id, key, value FROM labels").fetchall()
        out: dict[str, dict[str, str]] = {}
        for r in rows:
            out.setdefault(r["material_id"], {})[r["key"]] = r["value"]
        return out

    def _row(self, row: sqlite3.Row, with_features: bool = True) -> dict[str, Any]:
        d = dict(row)
        d["root"] = self._from_stored(d["root"])
        d["artifacts"] = json.loads(d["artifacts"])
        for a in d["artifacts"]:
            a["path"] = self._from_stored(a["path"])
        if with_features and d.get("features"):
            d["features"] = json.loads(d["features"])
        elif not with_features:
            d.pop("features", None)
        return d
