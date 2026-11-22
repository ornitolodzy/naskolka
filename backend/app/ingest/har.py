from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass, field
from urllib.parse import urlparse

from ..features.infra import is_public_cdn_host


@dataclass
class HarResult:
    landing_url: str | None = None
    urls: list[str] = field(default_factory=list)
    document_urls: list[str] = field(default_factory=list)
    redirects: list[tuple[str, str]] = field(default_factory=list)
    hosts: dict[str, int] = field(default_factory=dict)
    ips: dict[str, list[str]] = field(default_factory=dict)
    server_headers: set[str] = field(default_factory=set)
    resource_hashes: dict[str, str] = field(default_factory=dict)
    resource_names: set[str] = field(default_factory=set)
    html_bodies: list[tuple[str, str]] = field(default_factory=list)
    script_bodies: list[tuple[str, str]] = field(default_factory=list)
    entries: int = 0
    failed: int = 0


_HASHABLE = ("javascript", "css", "image/", "font", "json")
_MAX_SCRIPT_CHARS = 400_000


def _decode(content: dict) -> bytes | None:
    text = content.get("text")
    if not text:
        return None
    if content.get("encoding") == "base64":
        try:
            return base64.b64decode(text)
        except ValueError:
            return None
    return text.encode("utf-8", errors="replace")


def parse_har(path: str) -> HarResult:
    with open(path, encoding="utf-8", errors="replace") as fh:
        data = json.load(fh)
    entries = data.get("log", {}).get("entries", [])
    entries = sorted(entries, key=lambda e: e.get("startedDateTime") or "")
    res = HarResult(entries=len(entries))

    for e in entries:
        req, resp = e.get("request", {}), e.get("response", {})
        url = req.get("url") or ""
        if not url.startswith("http"):
            continue
        host = (urlparse(url).hostname or "").lower()
        status = int(resp.get("status") or 0)
        mime = ((resp.get("content") or {}).get("mimeType") or "").lower()
        res.urls.append(url)
        res.hosts[host] = res.hosts.get(host, 0) + 1
        if status == 0 or status >= 400:
            res.failed += 1

        ip = (e.get("serverIPAddress") or "").strip("[]")
        if ip:
            res.ips.setdefault(ip, [])
            if host not in res.ips[ip]:
                res.ips[ip].append(host)

        location = resp.get("redirectURL") or ""
        if 300 <= status < 400 and status != 304 and location:
            res.redirects.append((url, location))

        for h in resp.get("headers", []):
            name = (h.get("name") or "").lower()
            if name in {"server", "x-powered-by", "x-generator", "via"}:
                val = (h.get("value") or "").strip()
                if val:
                    res.server_headers.add(f"{name}:{val.lower()[:60]}")

        if "text/html" in mime and status == 200:
            res.document_urls.append(url)
            if res.landing_url is None:
                res.landing_url = url
            body = _decode(resp.get("content") or {})
            if body:
                res.html_bodies.append((url, body.decode("utf-8", errors="replace")))
            continue

        if any(k in mime for k in _HASHABLE) and not is_public_cdn_host(host):
            body = _decode(resp.get("content") or {})
            if body and len(body) > 512:
                res.resource_hashes[hashlib.sha1(body).hexdigest()] = url
            name = urlparse(url).path.rsplit("/", 1)[-1]
            if name and "." in name:
                res.resource_names.add(name.lower())
            if body and "javascript" in mime:
                res.script_bodies.append((url, body[:_MAX_SCRIPT_CHARS].decode("utf-8", errors="replace")))

    if res.landing_url is None and res.urls:
        res.landing_url = res.urls[0]
    return res
