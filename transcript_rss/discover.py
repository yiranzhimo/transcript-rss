from __future__ import annotations

import calendar
import re
from datetime import datetime, timezone
from typing import Any

import feedparser
import httpx
from defusedxml import ElementTree

from .models import DiscoveredItem, SourceConfig, TranscriptLink
from .utils import parse_datetime, utc_now

PODCAST_NS = "https://podcastindex.org/namespace/1.0"


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


def discover_source(
    source: SourceConfig,
    client: httpx.Client,
    source_state: dict[str, Any],
) -> list[DiscoveredItem]:
    if source.type == "podcast":
        return discover_podcast(source, client, source_state)
    raise ValueError(f"unsupported source type: {source.type}")
