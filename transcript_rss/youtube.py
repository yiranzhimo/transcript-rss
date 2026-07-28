from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def youtube_options(**overrides: Any) -> dict[str, Any]:
    """Build shared yt-dlp options for EJS, PO tokens, cookies, and proxies."""
    options: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "js_runtimes": {"deno": {}, "node": {}},
    }

    cookies_file = os.getenv("YOUTUBE_COOKIES_FILE", "").strip()
    if cookies_file:
        path = Path(cookies_file).expanduser()
        if not path.is_file():
            raise FileNotFoundError(f"YOUTUBE_COOKIES_FILE does not exist: {path}")
        options["cookiefile"] = str(path)

    proxy = os.getenv("YOUTUBE_PROXY", "").strip()
    if proxy:
        options["proxy"] = proxy

    provider_url = os.getenv("YOUTUBE_POT_PROVIDER_URL", "").strip()
    if provider_url:
        options["extractor_args"] = {
            "youtubepot-bgutilhttp": {"base_url": [provider_url.rstrip("/")]}
        }

    options.update(overrides)
    return options
