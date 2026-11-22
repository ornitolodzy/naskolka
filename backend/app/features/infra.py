from __future__ import annotations

import ipaddress
import json
import re
import socket
from functools import lru_cache
from pathlib import Path

import tldextract

_extract = tldextract.TLDExtract(suffix_list_urls=(), cache_dir=None)

PUBLIC_HOSTS = {
    "cdnjs.cloudflare.com", "cdn.jsdelivr.net", "unpkg.com", "code.jquery.com", "ajax.googleapis.com",
    "fonts.googleapis.com", "fonts.gstatic.com", "www.gstatic.com", "connect.facebook.net", "www.facebook.com",
    "facebook.com", "www.google.com", "www.google.pl", "google.com", "www.googletagmanager.com",
    "www.google-analytics.com", "googleads.g.doubleclick.net", "ad.doubleclick.net", "stats.g.doubleclick.net",
    "translate.googleapis.com", "translate.google.com", "translate-pa.googleapis.com", "images.unsplash.com",
    "maps.googleapis.com", "maps.gstatic.com", "cdn.tailwindcss.com", "stackpath.bootstrapcdn.com",
    "maxcdn.bootstrapcdn.com", "use.fontawesome.com", "kit.fontawesome.com", "player.vimeo.com",
    "www.youtube.com", "i.ytimg.com", "static.cloudflareinsights.com", "challenges.cloudflare.com",
    "analytics.tiktok.com", "mc.yandex.ru", "open.er-api.com", "api.ipify.org", "ipapi.co",
}
PUBLIC_SUFFIXES = (
    ".fbcdn.net", ".googleusercontent.com", ".googlesyndication.com", ".doubleclick.net",
    ".gstatic.com", ".googleapis.com", ".cloudfront.net", ".akamaihd.net",
)

_SHARED_NETS = {
    "cloudflare": [
        "173.245.48.0/20", "103.21.244.0/22", "103.22.200.0/22", "103.31.4.0/22", "141.101.64.0/18",
        "108.162.192.0/18", "190.93.240.0/20", "188.114.96.0/20", "197.234.240.0/22", "198.41.128.0/17",
        "162.158.0.0/15", "104.16.0.0/13", "104.24.0.0/14", "172.64.0.0/13", "131.0.72.0/22",
    ],
    "fastly": ["151.101.0.0/16", "146.75.0.0/16", "199.232.0.0/16"],
    "google": ["142.250.0.0/15", "142.251.0.0/16", "172.253.0.0/16", "216.58.192.0/19", "172.217.0.0/16"],
    "meta": ["57.144.0.0/14", "157.240.0.0/16", "31.13.24.0/21", "31.13.64.0/18", "179.60.192.0/22"],
    "bunnycdn": ["79.127.128.0/17", "185.93.0.0/22", "89.187.160.0/19"],
    "aws": ["63.176.0.0/12", "3.0.0.0/9", "52.0.0.0/10", "18.128.0.0/9"],
}
_NETS = [(name, ipaddress.ip_network(n)) for name, nets in _SHARED_NETS.items() for n in nets]

TRACKER_PATTERNS: dict[str, re.Pattern[str]] = {
    "fb_pixel": re.compile(r"fbq\(\s*['\"]init['\"]\s*,\s*['\"]?(\d{10,20})"),
    "fb_pixel_img": re.compile(r"facebook\.com/tr\?id=(\d{10,20})"),
    "gtm": re.compile(r"\b(GTM-[A-Z0-9]{5,8})\b"),
    "google_ads": re.compile(r"\b(AW-\d{8,12})\b"),
    "ga4": re.compile(r"\b(G-[A-Z0-9]{8,12})\b"),
    "ua": re.compile(r"\b(UA-\d{5,10}-\d{1,3})\b"),
    "tiktok_pixel": re.compile(r"ttq\.load\(\s*['\"]([A-Z0-9]{15,25})"),
    "yandex_metrica": re.compile(r"\bym\(\s*(\d{7,10})\s*,"),
    "conversion_id": re.compile(r"pagead/(?:1p-)?conversion/(\d{8,12})"),
    "keitaro_like": re.compile(r"\b(?:land_id|_camp_id|lpkey)=([\w-]{2,40})"),
    "phone_pl": re.compile(r"(?<!\d)(\+48[\s-]?\d{3}[\s-]?\d{3}[\s-]?\d{3})(?!\d)"),
    "email": re.compile(r"\b([A-Za-z0-9._%+-]{2,40}@[A-Za-z0-9-]{2,40}\.[a-z]{2,10})\b"),
}
_EMAIL_NOISE = re.compile(r"(\.png|\.jpg|\.webp|\.svg|example\.|sentry|wixpress|@2x|@3x|mhtml\.blink)", re.I)


def is_public_cdn_host(host: str) -> bool:
    host = (host or "").lower()
    return host in PUBLIC_HOSTS or host.endswith(PUBLIC_SUFFIXES)


def registrable_domain(host: str) -> str:
    host = (host or "").lower().strip(".")
    if not host:
        return ""
    ext = _extract(host)
    if not ext.suffix:
        return host
    return f"{ext.domain}.{ext.suffix}" if ext.domain else host


def tld(host: str) -> str:
    return _extract(host or "").suffix or ""


@lru_cache(maxsize=4096)
def shared_network(ip: str) -> str | None:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return None
    for name, net in _NETS:
        if addr.version == net.version and addr in net:
            return name
    return None


def find_trackers(text: str) -> dict[str, set[str]]:
    found: dict[str, set[str]] = {}
    if not text:
        return found
    for kind, pat in TRACKER_PATTERNS.items():
        for m in pat.findall(text):
            val = (m if isinstance(m, str) else m[0]).strip()
            if kind == "email" and _EMAIL_NOISE.search(val):
                continue
            if kind == "phone_pl":
                val = re.sub(r"[\s-]", "", val)
            found.setdefault("fb_pixel" if kind == "fb_pixel_img" else kind, set()).add(val)
    return found


class RdapClient:

    def __init__(self, cache_dir: Path, enabled: bool):
        self.enabled = enabled
        self.path = cache_dir / "rdap.json"
        cache_dir.mkdir(parents=True, exist_ok=True)
        try:
            self.cache: dict[str, dict] = json.loads(self.path.read_text("utf-8"))
        except (OSError, ValueError):
            self.cache = {}

    def lookup(self, domain: str) -> dict | None:
        if domain in self.cache:
            return self.cache[domain]
        if not self.enabled:
            return None
        import httpx

        info: dict = {"domain": domain}
        try:
            r = httpx.get(f"https://rdap.org/domain/{domain}", timeout=8, follow_redirects=True)
            if r.status_code == 200:
                data = r.json()
                for ev in data.get("events", []):
                    if ev.get("eventAction") in {"registration", "expiration", "last changed"}:
                        info[ev["eventAction"].replace(" ", "_")] = ev.get("eventDate")
                info["nameservers"] = sorted(
                    ns.get("ldhName", "").lower() for ns in data.get("nameservers", []) if ns.get("ldhName")
                )
                for ent in data.get("entities", []):
                    if "registrar" in (ent.get("roles") or []):
                        vcard = (ent.get("vcardArray") or [None, []])[1]
                        for item in vcard:
                            if item and item[0] == "fn":
                                info["registrar"] = item[3]
            else:
                info["rdap_status"] = r.status_code
        except Exception as exc:
            info["rdap_error"] = type(exc).__name__
        try:
            info["a_records"] = sorted({ai[4][0] for ai in socket.getaddrinfo(domain, 443, socket.AF_INET)})
        except OSError:
            info["a_records"] = []
        self.cache[domain] = info
        try:
            self.path.write_text(json.dumps(self.cache, ensure_ascii=False, indent=1), "utf-8")
        except OSError:
            pass
        return info
