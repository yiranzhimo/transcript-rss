from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def slugify(value: str, fallback: str = "item") -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9_-]+", "-", value)
    value = re.sub(r"-{2,}", "-", value).strip("-_")
    return value[:80] or fallback


def stable_item_slug(source_id: str, external_id: str) -> str:
    digest = hashlib.sha256(external_id.encode("utf-8")).hexdigest()[:12]
    return f"{slugify(source_id)}-{digest}"


def normalize_language(value: str | None) -> str:
    if not value:
        return "und"
    normalized = value.strip().lower().replace("_", "-")
    if normalized in {"english", "eng"}:
        return "en"
    if normalized in {"chinese", "mandarin", "cmn", "zho", "chi"}:
        return "zh"
    return normalized


def is_english(value: str | None) -> bool:
    return normalize_language(value).split("-", 1)[0] == "en"


def is_chinese(value: str | None) -> bool:
    return normalize_language(value).split("-", 1)[0] == "zh"


def detect_text_language(text: str) -> str:
    latin = len(re.findall(r"[A-Za-z]", text))
    cjk = len(re.findall(r"[\u3400-\u9fff]", text))
    if cjk >= 2 and cjk >= latin * 0.15:
        return "zh"
    if latin >= 5 and latin > cjk * 2:
        return "en"
    return "und"


def parse_datetime(value: str | None) -> datetime:
    if not value:
        return utc_now()
    normalized = value.strip().replace("Z", "+00:00")
    if re.fullmatch(r"\d{10}(?:\.\d+)?", normalized):
        return datetime.fromtimestamp(float(normalized), tz=timezone.utc)
    try:
        result = datetime.fromisoformat(normalized)
    except ValueError:
        if re.fullmatch(r"\d{8}", normalized):
            result = datetime.strptime(normalized, "%Y%m%d")
        else:
            return utc_now()
    if result.tzinfo is None:
        result = result.replace(tzinfo=timezone.utc)
    return result.astimezone(timezone.utc)


def format_timestamp(seconds: float) -> str:
    total = max(0, int(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"
