from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlparse

ID_PARAMS = {
    "pxl": "fb_pixel",
    "pixel": "fb_pixel",
    "fbpixel": "fb_pixel",
    "acc": "ad_account_tag",
    "land_id": "landing_id",
    "_camp_id": "tracker_campaign",
    "_trk": "tracker_tag",
    "lpkey": "lp_key",
    "trafficsource": "traffic_source",
    "utm_campaign": "utm_campaign",
    "adset_name": "adset_name",
    "ad_name": "ad_name",
    "user_id": "tracker_user",
}
CLICK_PARAMS = {"fbclid", "gclid", "ttclid", "clickid", "click_id", "subid", "sub_id", "ad_id", "utm_id",
                "utm_content", "utm_term", "utm_medium", "key", "upd_clickid", "random", "uuid"}
NOISE_PARAMS = {"fbclid", "gclid", "ttclid", "_", "random", "cb", "v", "ver"}


def value_shape(v: str) -> str:
    if not v:
        return "E"
    if v.isdigit():
        return f"D{len(v)}"
    if re.fullmatch(r"[a-z0-9]+", v):
        return f"Lx{len(v)}"
    if re.fullmatch(r"[A-Z0-9]+", v):
        return f"Ux{len(v)}"
    if re.fullmatch(r"[A-Za-z0-9]+", v):
        return f"Mx{len(v)}"
    if re.fullmatch(r"[0-9a-f-]{36}", v):
        return "UUID"
    return "S"


def path_shape(path: str) -> str:
    parts = [p for p in path.split("/") if p]
    out = []
    for p in parts[:4]:
        if re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", p):
            out.append("{uuid}")
        elif re.fullmatch(r"\d+", p):
            out.append("{n}")
        elif len(p) >= 10 and sum(ch.isdigit() for ch in p) >= 3:
            out.append(f"{{tok{len(p)}}}")
        elif re.fullmatch(r"[A-Za-z0-9]{6,12}", p) and not p.isalpha():
            out.append(f"{{id{len(p)}}}")
        else:
            out.append(p.lower()[:30])
    return "/" + "/".join(out)


def url_features(url: str) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    try:
        u = urlparse(url)
    except ValueError:
        return out
    params = [(k, v) for k, v in parse_qsl(u.query, keep_blank_values=True) if k.lower() not in NOISE_PARAMS]
    if params:
        keys = sorted({k.lower() for k, _ in params})
        if len(keys) >= 3:
            out.setdefault("url_param_keys", set()).add(",".join(keys))
        template = "&".join(f"{k.lower()}={value_shape(v)}" for k, v in sorted(params, key=lambda kv: kv[0].lower()))
        if len(params) >= 3:
            out.setdefault("url_template", set()).add(template)
        for k, v in params:
            kl = k.lower()
            if kl in ID_PARAMS and v and not v.startswith("{"):
                val = v.strip()[:80]
                if kl == "acc":
                    out.setdefault("ad_account_prefix", set()).add(val.split("_")[0])
                out.setdefault(ID_PARAMS[kl], set()).add(val)
            if kl in {"clickid", "click_id", "upd_clickid"} and v:
                out.setdefault("clickid_shape", set()).add(value_shape(v))
            if kl == "utm_source" and v:
                out.setdefault("traffic_platform", set()).add(v.lower()[:20])
            if kl in {"placement", "utm_placement"} and v:
                out.setdefault("placement", set()).add(v.lower()[:40])
    ps = path_shape(u.path or "/")
    if ps.count("/") >= 2 or "{" in ps:
        out.setdefault("path_shape", set()).add(ps)
    return out
