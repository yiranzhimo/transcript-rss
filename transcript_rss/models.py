from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class SourceConfig:
    id: str
    type: str
    url: str
    title: str | None = None
    language: str = "auto"
    enabled: bool = True
    max_items_per_run: int = 1
    scan_limit: int = 15


@dataclass(slots=True)
class SiteConfig:
    title: str
    description: str
    base_url: str
    output_dir: Path
    state_file: Path
    feed_items: int = 30
    content_mode: str = "full"
    content_max_characters: int = 120_000


@dataclass(slots=True)
class TranslationConfig:
    enabled: bool = True
    api_base: str = "https://openrouter.ai/api/v1"
    model: str = "openai/gpt-4o-mini"
    api_key_env: str = "OPENROUTER_API_KEY"
    chunk_characters: int = 6_000


@dataclass(slots=True)
class TranscriptionConfig:
    enabled: bool = True
    model: str = "small"
    device: str = "cpu"
    compute_type: str = "int8"
    max_download_mb: int = 500


@dataclass(slots=True)
class AppConfig:
    site: SiteConfig
    translation: TranslationConfig
    transcription: TranscriptionConfig
    sources: list[SourceConfig]
    config_path: Path


@dataclass(slots=True)
class TranscriptLink:
    url: str
    media_type: str | None = None
    language: str | None = None
    rel: str | None = None


@dataclass(slots=True)
class DiscoveredItem:
    source_id: str
    source_type: str
    external_id: str
    title: str
    url: str
    published_at: datetime
    description: str = ""
    media_url: str | None = None
    transcript_links: list[TranscriptLink] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_state_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "source_type": self.source_type,
            "external_id": self.external_id,
            "title": self.title,
            "url": self.url,
            "published_at": self.published_at.astimezone(timezone.utc).isoformat(),
            "description": self.description,
        }


@dataclass(slots=True)
class Segment:
    start: float
    end: float
    text: str
    speaker: str | None = None


@dataclass(slots=True)
class Transcript:
    language: str
    segments: list[Segment]
    provenance: str

    @property
    def text(self) -> str:
        return "\n".join(segment.text.strip() for segment in self.segments if segment.text.strip())
