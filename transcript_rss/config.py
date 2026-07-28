from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from .models import (
    AppConfig,
    SiteConfig,
    SourceConfig,
    TranscriptionConfig,
    TranslationConfig,
)


class ConfigError(ValueError):
    pass


def _environment_value(name: str, fallback: str) -> str:
    value = os.getenv(name, "").strip()
    return value or fallback


def _mapping(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigError(f"{name} must be a mapping")
    return value


def load_config(path: str | Path) -> AppConfig:
    config_path = Path(path).resolve()
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    raw = _mapping(raw, "config")

    site_raw = _mapping(raw.get("site", {}), "site")
    base_url = _environment_value(
        "SITE_BASE_URL",
        str(site_raw.get("base_url", "")),
    ).rstrip("/")
    if not base_url or base_url == "https://USERNAME.github.io/transcript-rss":
        raise ConfigError("site.base_url must be set to the final GitHub Pages URL")

    root = config_path.parent
    site = SiteConfig(
        title=str(site_raw.get("title", "Transcript RSS")),
        description=str(site_raw.get("description", "Chinese transcripts for podcasts and videos")),
        base_url=base_url,
        output_dir=(root / str(site_raw.get("output_dir", "docs"))).resolve(),
        state_file=(root / str(site_raw.get("state_file", "data/state.json"))).resolve(),
        feed_items=max(1, int(site_raw.get("feed_items", 30))),
        content_mode=str(site_raw.get("content_mode", "full")),
        content_max_characters=max(1_000, int(site_raw.get("content_max_characters", 120_000))),
    )
    if site.content_mode not in {"full", "summary", "link"}:
        raise ConfigError("site.content_mode must be full, summary, or link")

    translation_raw = _mapping(raw.get("translation", {}), "translation")
    translation = TranslationConfig(
        enabled=bool(translation_raw.get("enabled", True)),
        api_base=_environment_value(
            "TRANSLATION_API_BASE",
            str(translation_raw.get("api_base", "https://openrouter.ai/api/v1")),
        ).rstrip("/"),
        model=_environment_value(
            "TRANSLATION_MODEL",
            _environment_value(
                "OPENROUTER_MODEL",
                str(translation_raw.get("model", "openai/gpt-4o-mini")),
            ),
        ),
        api_key_env=str(translation_raw.get("api_key_env", "OPENROUTER_API_KEY")),
        chunk_characters=max(500, int(translation_raw.get("chunk_characters", 6_000))),
    )

    transcription_raw = _mapping(raw.get("transcription", {}), "transcription")
    transcription = TranscriptionConfig(
        enabled=bool(transcription_raw.get("enabled", True)),
        model=str(transcription_raw.get("model", "small")),
        device=str(transcription_raw.get("device", "cpu")),
        compute_type=str(transcription_raw.get("compute_type", "int8")),
        max_download_mb=max(10, int(transcription_raw.get("max_download_mb", 500))),
    )

    source_rows = raw.get("sources")
    if not isinstance(source_rows, list) or not source_rows:
        raise ConfigError("sources must contain at least one source")

    sources: list[SourceConfig] = []
    ids: set[str] = set()
    for index, row in enumerate(source_rows):
        item = _mapping(row, f"sources[{index}]")
        source_id = str(item.get("id", "")).strip()
        source_type = str(item.get("type", "")).strip().lower()
        url = str(item.get("url", "")).strip()
        if not source_id or not source_id.replace("-", "").replace("_", "").isalnum():
            raise ConfigError(f"sources[{index}].id must contain letters, digits, - or _")
        if source_id in ids:
            raise ConfigError(f"duplicate source id: {source_id}")
        if source_type not in {"podcast", "youtube"}:
            raise ConfigError(f"sources[{index}].type must be podcast or youtube")
        if not url:
            raise ConfigError(f"sources[{index}].url is required")
        ids.add(source_id)
        sources.append(
            SourceConfig(
                id=source_id,
                type=source_type,
                url=url,
                title=str(item["title"]) if item.get("title") else None,
                language=str(item.get("language", "auto")),
                enabled=bool(item.get("enabled", True)),
                max_items_per_run=max(1, int(item.get("max_items_per_run", 1))),
                scan_limit=max(1, int(item.get("scan_limit", 15))),
            )
        )

    return AppConfig(
        site=site,
        translation=translation,
        transcription=transcription,
        sources=sources,
        config_path=config_path,
    )
