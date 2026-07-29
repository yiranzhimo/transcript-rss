from __future__ import annotations

import hashlib
import time
from typing import Any
from urllib.parse import urlencode

import httpx

NAV_URL = "https://api.bilibili.com/x/web-interface/nav"
DYNAMIC_FEED_URL = "https://api.bilibili.com/x/polymer/web-dynamic/v1/feed/space"

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.bilibili.com/",
    "Origin": "https://www.bilibili.com",
}

# Bilibili's WBI signature scrambles the mixin key with this fixed table.
# See https://github.com/SocialSisterYi/bilibili-API-collect (wbi sign docs).
MIXIN_KEY_ENC_TAB = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49,
    33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16, 24, 55, 40,
    61, 26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11,
    36, 20, 34, 44, 52,
]


def _mixin_key(orig: str) -> str:
    return "".join(orig[index] for index in MIXIN_KEY_ENC_TAB if index < len(orig))[:32]


def _fetch_wbi_keys(client: httpx.Client) -> tuple[str, str]:
    response = client.get(NAV_URL, headers=DEFAULT_HEADERS, timeout=15)
    response.raise_for_status()
    wbi_img = ((response.json().get("data") or {}).get("wbi_img")) or {}
    img_key = str(wbi_img.get("img_url", "")).rsplit("/", 1)[-1].split(".", 1)[0]
    sub_key = str(wbi_img.get("sub_url", "")).rsplit("/", 1)[-1].split(".", 1)[0]
    if not img_key or not sub_key:
        raise ValueError("could not resolve Bilibili WBI signing keys")
    return img_key, sub_key


def _sign_params(params: dict[str, str], img_key: str, sub_key: str) -> dict[str, str]:
    mixin_key = _mixin_key(img_key + sub_key)
    signed = dict(sorted({**params, "wts": str(int(time.time()))}.items()))
    signed = {key: "".join(ch for ch in value if ch not in "!'()*") for key, value in signed.items()}
    query = urlencode(signed)
    signed["w_rid"] = hashlib.md5((query + mixin_key).encode("utf-8")).hexdigest()
    return signed


def fetch_video_dynamics(client: httpx.Client, uid: str, limit: int) -> list[dict[str, Any]]:
    """Fetch a Bilibili uploader's recent video uploads via the public dynamic feed.

    Uses the same `x/polymer/web-dynamic/v1/feed/space` endpoint RSSHub's
    Bilibili route relies on, rather than scraping the space page like
    yt-dlp does: it's a lighter, more commonly used official API and is
    far less likely to trip Bilibili's anti-scraping risk control.
    """
    img_key, sub_key = _fetch_wbi_keys(client)
    headers = {**DEFAULT_HEADERS, "Referer": f"https://space.bilibili.com/{uid}/dynamic"}
    results: list[dict[str, Any]] = []
    offset = ""
    for _ in range(5):
        params = _sign_params(
            {"host_mid": uid, "offset": offset, "platform": "web", "features": "itemOpusStyle"},
            img_key,
            sub_key,
        )
        response = client.get(DYNAMIC_FEED_URL, params=params, headers=headers, timeout=20)
        response.raise_for_status()
        payload = response.json()
        if payload.get("code") != 0:
            raise ValueError(f"Bilibili dynamic feed error for uid {uid}: {payload.get('message')}")
        data = payload.get("data") or {}
        for item in data.get("items") or []:
            if item.get("type") != "DYNAMIC_TYPE_AV":
                continue
            modules = item.get("modules") or {}
            archive = (modules.get("module_dynamic") or {}).get("major", {}).get("archive") or {}
            bvid = archive.get("bvid")
            if not bvid:
                continue
            author = modules.get("module_author") or {}
            results.append(
                {
                    "bvid": str(bvid),
                    "title": str(archive.get("title") or ""),
                    "description": str(archive.get("desc") or ""),
                    "pub_ts": int(author.get("pub_ts") or 0),
                    "author": str(author.get("name") or ""),
                }
            )
        if len(results) >= limit:
            break
        offset = str(data.get("offset") or "")
        if not data.get("has_more") or not offset:
            break
    return results[:limit]
