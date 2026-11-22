from __future__ import annotations

import email
import email.policy
import re
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Comment

_SAVED_FROM = re.compile(r"saved from url=\(\d+\)(\S+)", re.IGNORECASE)
_WS = re.compile(r"\s+")
_GENERATED_CLASS = re.compile(r"^(css|sc|jsx|svelte|emotion|tw)-[a-z0-9]{4,}$|^[a-z]{1,2}\d+[a-z0-9]*$", re.I)


@dataclass
class HtmlResult:
    saved_from: str | None = None
    title: str = ""
    description: str = ""
    meta: dict[str, str] = field(default_factory=dict)
    text: str = ""
    headings: list[str] = field(default_factory=list)
    links: list[str] = field(default_factory=list)
    form_actions: list[str] = field(default_factory=list)
    script_srcs: list[str] = field(default_factory=list)
    image_srcs: list[str] = field(default_factory=list)
    iframe_srcs: list[str] = field(default_factory=list)
    classes: set[str] = field(default_factory=set)
    ids: set[str] = field(default_factory=set)
    tag_shape: list[str] = field(default_factory=list)
    raw: str = ""


def _clean(s: str) -> str:
    return _WS.sub(" ", s or "").strip()


def parse_html(raw: str, base_url: str | None = None) -> HtmlResult:
    res = HtmlResult(raw=raw)
    m = _SAVED_FROM.search(raw[:4000])
    if m and m.group(1).startswith("http"):
        res.saved_from = m.group(1)
    base = base_url or res.saved_from

    soup = BeautifulSoup(raw, "lxml")
    if soup.title and soup.title.string:
        res.title = _clean(soup.title.string)

    for tag in soup.find_all("meta"):
        key = (tag.get("property") or tag.get("name") or "").lower()
        val = tag.get("content")
        if key and val:
            res.meta[key] = _clean(val)[:500]
    res.description = res.meta.get("description") or res.meta.get("og:description", "")
    canonical = soup.find("link", rel="canonical")
    if canonical and canonical.get("href"):
        res.meta["canonical"] = canonical["href"]

    def absolute(u: str | None) -> str | None:
        if not u or u.startswith(("data:", "javascript:", "mailto:", "tel:", "#")):
            return None
        return urljoin(base, u) if base else u

    for a in soup.find_all("a", href=True):
        if (u := absolute(a["href"])) and u.startswith("http"):
            res.links.append(u)
    for f in soup.find_all("form"):
        if (u := absolute(f.get("action"))):
            res.form_actions.append(u)
    for s in soup.find_all("script", src=True):
        if (u := absolute(s["src"])):
            res.script_srcs.append(u)
    for i in soup.find_all("img"):
        src = i.get("src") or i.get("data-src") or i.get("data-lazy-src")
        if (u := absolute(src)):
            res.image_srcs.append(u)
    for i in soup.find_all("iframe", src=True):
        if (u := absolute(i["src"])):
            res.iframe_srcs.append(u)

    body = soup.body or soup
    for el in body.find_all(True):
        for c in el.get("class") or []:
            if 2 < len(c) < 40 and not _GENERATED_CLASS.match(c):
                res.classes.add(c.lower())
        if el.get("id") and len(el["id"]) < 40:
            res.ids.add(el["id"].lower())
    res.tag_shape = [el.name for el in body.find_all(True)][:4000]

    for h in body.find_all(["h1", "h2", "h3"]):
        t = _clean(h.get_text(" "))
        if t:
            res.headings.append(t[:300])

    for bad in soup(["script", "style", "noscript", "template", "svg"]):
        bad.decompose()
    for c in soup.find_all(string=lambda s: isinstance(s, Comment)):
        c.extract()
    res.text = _clean(body.get_text(" "))[:200_000]
    return res


def mhtml_documents(path: str) -> list[tuple[str | None, str]]:
    with open(path, "rb") as fh:
        msg = email.message_from_binary_file(fh, policy=email.policy.default)
    docs: list[tuple[str | None, str]] = []
    for part in msg.walk():
        if part.get_content_type() == "text/html":
            try:
                docs.append((part.get("Content-Location"), part.get_content()))
            except (LookupError, ValueError):
                payload = part.get_payload(decode=True) or b""
                docs.append((part.get("Content-Location"), payload.decode("utf-8", errors="replace")))
    return docs


def host_of(url: str) -> str:
    return (urlparse(url).hostname or "").lower()
