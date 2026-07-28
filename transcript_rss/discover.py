from __future__ import annotations

import calendar
import re
from datetime import datetime, timezone
from typing import Any

import feedparser
import httpx
from defusedxml import ElementTree
from yt_dlp import YoutubeDL

from .models import DiscoveredItem, SourceConfig, TranscriptLink
from .utils import parse_datetime, utc_now
from .youtube import youtube_options

PODCAST_NS = "https://podcastindex.org/namespace/1.0"
YOUTUBE_CHANNEL_ID_RE = re.compile(r"(UC[A-Za-z0-9_-]{22})")


def _datetime_from_entry(entry: Any) -> datetime:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed:
        return datetime.fromtimestamp(calendar.timegm(parsed), tz=timezone.utc)
    return parse_datetime(entry.get("published") or entry.get("updated"))


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].split(":", 1)[-1]


def _podcast_transcript_map(raw_xml: bytes) -> dict[str, list[TranscriptLink]]:
    result: dict[str, list[TranscriptLink]] = {}
    try:
        root = ElementTree.fromstring(raw_xml)
    except ElementTree.ParseError:
        return result

    for item in root.iter():
        if _local_name(item.tag) not in {"item", "entry"}:
            continue
        identifiers: list[str] = []
        links: list[TranscriptLink] = []
        for child in list(item):
            name = _local_name(child.tag)
            text = (child.text or "").strip()
            if name in {"guid", "id"} and text:
                identifiers.append(text)
            elif name == "link":
                href = child.attrib.get("href") or text
                if href:
                    identifiers.append(href)
            elif name == "transcript":
                url = child.attrib.get("url")
                if url:
                    links.append(
                        TranscriptLink(
                            url=url,
                            media_type=child.attrib.get("type"),
                            language=child.attrib.get("language"),
                            rel=child.attrib.get("rel"),
                        )
                    )
        for identifier in identifiers:
            if links:
                result[identifier] = links
    return result


def _conditional_headers(source_state: dict[str, Any]) -> dict[str, str]:
    headers = {"User-Agent": "transcript-rss/0.1 (+personal feed reader)"}
    if source_state.get("force_refresh"):
        return headers
    if source_state.get("etag"):
        headers["If-None-Match"] = str(source_state["etag"])
    if source_state.get("last_modified"):
        headers["If-Modified-Since"] = str(source_state["last_modified"])
    return headers


def discover_podcast(
    source: SourceConfig,
    client: httpx.Client,
    source_state: dict[str, Any],
) -> list[DiscoveredItem]:
    response = client.get(source.url, headers=_conditional_headers(source_state))
    if response.status_code == 304:
        source_state["last_checked_at"] = utc_now().isoformat()
        return []
    response.raise_for_status()
    if response.headers.get("etag"):
        source_state["etag"] = response.headers["etag"]
    if response.headers.get("last-modified"):
        source_state["last_modified"] = response.headers["last-modified"]
    source_state["last_checked_at"] = utc_now().isoformat()

    parsed = feedparser.parse(response.content)
    transcript_map = _podcast_transcript_map(response.content)
    discovered: list[DiscoveredItem] = []
    for entry in parsed.entries[: source.scan_limit]:
        url = str(entry.get("link", "")).strip()
        external_id = str(entry.get("id") or url).strip()
        if not external_id:
            continue
        enclosures = entry.get("enclosures") or []
        media_url = None
        if enclosures:
            media_url = enclosures[0].get("href") or enclosures[0].get("url")
        transcript_links = transcript_map.get(external_id) or transcript_map.get(url) or []
        discovered.append(
            DiscoveredItem(
                source_id=source.id,
                source_type="podcast",
                external_id=external_id,
                title=str(entry.get("title", external_id)),
                url=url or external_id,
                published_at=_datetime_from_entry(entry),
                description=str(entry.get("summary", "")),
                media_url=str(media_url) if media_url else None,
                transcript_links=transcript_links,
                metadata={"feed_title": str(parsed.feed.get("title", source.title or source.id))},
            )
        )
    return discovered


def _youtube_channel_feed_url(url: str) -> str | None:
    if "feeds/videos.xml" in url:
        return url
    match = YOUTUBE_CHANNEL_ID_RE.search(url)
    if match:
        return f"https://www.youtube.com/feeds/videos.xml?channel_id={match.group(1)}"
    return None


def _discover_youtube_feed(
    source: SourceConfig,
    feed_url: str,
    client: httpx.Client,
    source_state: dict[str, Any],
) -> list[DiscoveredItem]:
    response = client.get(feed_url, headers=_conditional_headers(source_state))
    if response.status_code == 304:
        source_state["last_checked_at"] = utc_now().isoformat()
        return []
    response.raise_for_status()
    if response.headers.get("etag"):
        source_state["etag"] = response.headers["etag"]
    if response.headers.get("last-modified"):
        source_state["last_modified"] = response.headers["last-modified"]
    source_state["last_checked_at"] = utc_now().isoformat()

    parsed = feedparser.parse(response.content)
    result: list[DiscoveredItem] = []
    for entry in parsed.entries[: source.scan_limit]:
        video_id = str(entry.get("yt_videoid") or entry.get("id", "")).split(":")[-1]
        if not video_id:
            continue
        url = str(entry.get("link") or f"https://www.youtube.com/watch?v={video_id}")
        result.append(
            DiscoveredItem(
                source_id=source.id,
                source_type="youtube",
                external_id=f"youtube:{video_id}",
                title=str(entry.get("title", video_id)),
                url=url,
                published_at=_datetime_from_entry(entry),
                description=str(entry.get("media_description", "")),
                metadata={
                    "video_id": video_id,
                    "channel_title": str(parsed.feed.get("title", source.title or source.id)),
                },
            )
        )
    return result


def _youtube_listing_url(url: str) -> str:
    clean = url.rstrip("/")
    if "/watch?" in clean or "/playlist?" in clean or clean.endswith(("/videos", "/streams")):
        return clean
    return f"{clean}/videos"


def _discover_youtube_with_ytdlp(source: SourceConfig) -> list[DiscoveredItem]:
    options = youtube_options(extract_flat="in_playlist")
    options.update(
        {
            "playlistend": source.scan_limit,
            "skip_download": True,
        }
    )
    with YoutubeDL(options) as downloader:
        info = downloader.extract_info(_youtube_listing_url(source.url), download=False)
    entries = info.get("entries") or ([info] if info else [])
    result: list[DiscoveredItem] = []
    for entry in entries[: source.scan_limit]:
        if not entry:
            continue
        video_id = str(entry.get("id", "")).strip()
        if not video_id:
            continue
        url = entry.get("webpage_url") or entry.get("url")
        if not url or not str(url).startswith("http"):
            url = f"https://www.youtube.com/watch?v={video_id}"
        published = parse_datetime(
            str(entry.get("timestamp") or entry.get("release_timestamp") or entry.get("upload_date") or "")
        )
        result.append(
            DiscoveredItem(
                source_id=source.id,
                source_type="youtube",
                external_id=f"youtube:{video_id}",
                title=str(entry.get("title") or video_id),
                url=str(url),
                published_at=published,
                description=str(entry.get("description") or ""),
                metadata={
                    "video_id": video_id,
                    "channel_title": str(
                        info.get("channel") or info.get("uploader") or source.title or source.id
                    ),
                },
            )
        )
    return result


def discover_youtube(
    source: SourceConfig,
    client: httpx.Client,
    source_state: dict[str, Any],
) -> list[DiscoveredItem]:
    feed_url = _youtube_channel_feed_url(source.url)
    if feed_url:
        return _discover_youtube_feed(source, feed_url, client, source_state)
    source_state["last_checked_at"] = utc_now().isoformat()
    return _discover_youtube_with_ytdlp(source)


def discover_source(
    source: SourceConfig,
    client: httpx.Client,
    source_state: dict[str, Any],
) -> list[DiscoveredItem]:
    if source.type == "podcast":
        return discover_podcast(source, client, source_state)
    if source.type == "youtube":
        return discover_youtube(source, client, source_state)
    raise ValueError(f"unsupported source type: {source.type}")
