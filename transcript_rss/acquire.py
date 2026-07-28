from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from yt_dlp import YoutubeDL

from .models import DiscoveredItem, Segment, SourceConfig, Transcript, TranscriptLink
from .utils import detect_text_language, is_chinese, is_english, normalize_language
from .youtube import youtube_options

TIMESTAMP_RE = re.compile(
    r"(?P<start>\d{1,2}:\d{2}(?::\d{2})?[.,]\d{3})\s+-->\s+"
    r"(?P<end>\d{1,2}:\d{2}(?::\d{2})?[.,]\d{3})"
)
TAG_RE = re.compile(r"<[^>]+>")


def _seconds(value: str) -> float:
    normalized = value.replace(",", ".")
    parts = normalized.split(":")
    if len(parts) == 2:
        minutes, seconds = parts
        return int(minutes) * 60 + float(seconds)
    hours, minutes, seconds = parts
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def _clean_caption_text(value: str) -> str:
    value = TAG_RE.sub("", value)
    return html.unescape(value).replace("\u200b", "").strip()


def _parse_vtt_or_srt(text: str) -> list[Segment]:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    segments: list[Segment] = []
    index = 0
    while index < len(lines):
        match = TIMESTAMP_RE.search(lines[index])
        if not match:
            index += 1
            continue
        start = _seconds(match.group("start"))
        end = _seconds(match.group("end"))
        index += 1
        text_lines: list[str] = []
        while index < len(lines) and lines[index].strip():
            cleaned = _clean_caption_text(lines[index])
            if cleaned:
                text_lines.append(cleaned)
            index += 1
        content = " ".join(text_lines).strip()
        if content and (not segments or content != segments[-1].text):
            segments.append(Segment(start=start, end=end, text=content))
        index += 1
    return segments


def _parse_youtube_json3(data: dict[str, Any]) -> list[Segment]:
    segments: list[Segment] = []
    for event in data.get("events", []):
        parts = event.get("segs") or []
        text = "".join(str(part.get("utf8", "")) for part in parts)
        text = " ".join(text.replace("\n", " ").split())
        if not text:
            continue
        start = float(event.get("tStartMs", 0)) / 1000
        end = start + float(event.get("dDurationMs", 0)) / 1000
        if not segments or text != segments[-1].text:
            segments.append(Segment(start=start, end=end, text=text))
    return segments


def _plain_segments(text: str) -> list[Segment]:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    if not paragraphs and text.strip():
        paragraphs = [text.strip()]
    return [Segment(start=0, end=0, text=paragraph) for paragraph in paragraphs]


def parse_transcript(
    content: bytes,
    media_type: str | None,
    url: str,
    language: str | None,
    provenance: str,
) -> Transcript:
    suffix = Path(urlparse(url).path).suffix.lower()
    normalized_type = (media_type or "").lower().split(";", 1)[0]
    if normalized_type == "application/json" or suffix == ".json":
        data = json.loads(content)
        segments = _parse_youtube_json3(data)
        if not segments and isinstance(data, dict):
            rows = data.get("segments") or data.get("transcript") or []
            for row in rows if isinstance(rows, list) else []:
                if not isinstance(row, dict):
                    continue
                text = str(row.get("text") or row.get("body") or "").strip()
                if text:
                    segments.append(
                        Segment(
                            start=float(row.get("start") or row.get("startTime") or 0),
                            end=float(row.get("end") or row.get("endTime") or 0),
                            text=text,
                            speaker=str(row.get("speaker")) if row.get("speaker") else None,
                        )
                    )
    else:
        text = content.decode("utf-8", errors="replace")
        if normalized_type in {"text/vtt", "application/x-subrip"} or suffix in {".vtt", ".srt"}:
            segments = _parse_vtt_or_srt(text)
        elif normalized_type == "text/html" or suffix in {".html", ".htm"}:
            soup = BeautifulSoup(text, "html.parser")
            for node in soup(["script", "style", "nav", "footer"]):
                node.decompose()
            paragraphs = "\n\n".join(
                node.get_text(" ", strip=True) for node in soup.find_all(["p", "li"]) if node.get_text(strip=True)
            )
            segments = _plain_segments(paragraphs or soup.get_text("\n", strip=True))
        else:
            segments = _plain_segments(text)
    if not segments:
        raise ValueError(f"transcript at {url} contained no readable text")
    detected = normalize_language(language)
    if detected == "und":
        detected = detect_text_language("\n".join(segment.text for segment in segments[:50]))
    return Transcript(language=detected, segments=segments, provenance=provenance)


def _transcript_link_priority(link: TranscriptLink) -> tuple[int, int]:
    language = normalize_language(link.language)
    if is_chinese(language):
        language_rank = 0
    elif is_english(language):
        language_rank = 1
    else:
        language_rank = 2
    media_type = (link.media_type or "").lower()
    type_rank = {
        "application/json": 0,
        "text/vtt": 1,
        "application/x-subrip": 2,
        "text/plain": 3,
        "text/html": 4,
    }.get(media_type, 5)
    return language_rank, type_rank


def fetch_podcast_transcript(
    item: DiscoveredItem,
    client: httpx.Client,
) -> Transcript | None:
    for link in sorted(item.transcript_links, key=_transcript_link_priority):
        try:
            response = client.get(link.url)
            response.raise_for_status()
            return parse_transcript(
                response.content,
                link.media_type or response.headers.get("content-type"),
                link.url,
                link.language,
                "publisher transcript",
            )
        except (httpx.HTTPError, ValueError, json.JSONDecodeError):
            continue
    return None


def _language_priority(language: str) -> tuple[int, str]:
    normalized = normalize_language(language)
    if is_chinese(normalized):
        return 0, normalized
    if is_english(normalized):
        return 1, normalized
    return 2, normalized


def _select_youtube_track(
    info: dict[str, Any],
) -> tuple[str, dict[str, Any], str] | None:
    for collection_name, provenance in (
        ("subtitles", "creator subtitles"),
        ("automatic_captions", "YouTube automatic captions"),
    ):
        collection = info.get(collection_name) or {}
        for language in sorted(collection, key=_language_priority):
            formats = collection.get(language) or []
            usable = [
                row
                for row in formats
                if row.get("url") and row.get("ext") in {"json3", "vtt", "srt"}
            ]
            usable.sort(key=lambda row: {"json3": 0, "vtt": 1, "srt": 2}.get(row.get("ext"), 9))
            if usable and _language_priority(language)[0] < 2:
                return language, usable[0], provenance
    return None


def fetch_youtube_transcript(
    item: DiscoveredItem,
    client: httpx.Client,
) -> tuple[Transcript | None, dict[str, Any]]:
    options = youtube_options(skip_download=True)
    with YoutubeDL(options) as downloader:
        info = downloader.extract_info(item.url, download=False)
    selected = _select_youtube_track(info)
    if not selected:
        return None, info
    language, track, provenance = selected
    response = client.get(track["url"])
    response.raise_for_status()
    transcript = parse_transcript(
        response.content,
        "application/json" if track.get("ext") == "json3" else f"text/{track.get('ext')}",
        track["url"],
        language,
        provenance,
    )
    return transcript, info


def fetch_bilibili_transcript(
    item: DiscoveredItem,
    client: httpx.Client,
) -> tuple[Transcript | None, dict[str, Any]]:
    options = youtube_options(skip_download=True)
    with YoutubeDL(options) as downloader:
        info = downloader.extract_info(item.url, download=False)
    for collection_name, provenance in (
        ("subtitles", "Bilibili subtitles"),
        ("automatic_captions", "Bilibili automatic captions"),
    ):
        collection = info.get(collection_name) or {}
        for language in sorted(collection, key=_language_priority):
            formats = collection.get(language) or []
            usable = [
                row for row in formats
                if row.get("url") and row.get("ext") in {"json3", "vtt", "srt"}
            ]
            if not usable:
                continue
            track = sorted(usable, key=lambda row: {"json3": 0, "vtt": 1, "srt": 2}.get(row.get("ext"), 9))[0]
            response = client.get(track["url"])
            response.raise_for_status()
            return parse_transcript(
                response.content,
                "application/json" if track.get("ext") == "json3" else f"text/{track.get('ext')}",
                track["url"],
                language,
                provenance,
            ), info
    return None, info


def download_podcast_audio(
    item: DiscoveredItem,
    client: httpx.Client,
    work_dir: Path,
    max_download_mb: int,
) -> Path:
    if not item.media_url:
        raise ValueError("podcast item has no audio enclosure")
    suffix = Path(urlparse(item.media_url).path).suffix or ".audio"
    output = work_dir / f"source{suffix[:10]}"
    limit = max_download_mb * 1024 * 1024
    size = 0
    with client.stream("GET", item.media_url) as response:
        response.raise_for_status()
        with output.open("wb") as handle:
            for chunk in response.iter_bytes():
                size += len(chunk)
                if size > limit:
                    raise ValueError(f"audio exceeds configured {max_download_mb} MB limit")
                handle.write(chunk)
    return output


def download_youtube_audio(
    item: DiscoveredItem,
    work_dir: Path,
) -> Path:
    output_template = str(work_dir / "source.%(ext)s")
    options = youtube_options(
        format="bestaudio/best",
        outtmpl=output_template,
        noplaylist=True,
    )
    with YoutubeDL(options) as downloader:
        info = downloader.extract_info(item.url, download=True)
        filename = Path(downloader.prepare_filename(info))
    if filename.exists():
        return filename
    candidates = list(work_dir.glob("source.*"))
    if not candidates:
        raise FileNotFoundError("yt-dlp completed without an audio file")
    return candidates[0]


def fetch_existing_transcript(
    source: SourceConfig,
    item: DiscoveredItem,
    client: httpx.Client,
) -> tuple[Transcript | None, dict[str, Any]]:
    if source.type == "podcast":
        return fetch_podcast_transcript(item, client), {}
    if source.type == "bilibili":
        return fetch_bilibili_transcript(item, client)
    return fetch_youtube_transcript(item, client)
