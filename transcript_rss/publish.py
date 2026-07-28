from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from .models import AppConfig, DiscoveredItem, SourceConfig, Transcript
from .utils import format_timestamp, stable_item_slug

CONTENT_NS = "http://purl.org/rss/1.0/modules/content/"
ATOM_NS = "http://www.w3.org/2005/Atom"
PODCAST_NS = "https://podcastindex.org/namespace/1.0"

ElementTree.register_namespace("content", CONTENT_NS)
ElementTree.register_namespace("atom", ATOM_NS)
ElementTree.register_namespace("podcast", PODCAST_NS)


def _markdown(transcript: Transcript) -> str:
    rows: list[str] = []
    for segment in transcript.segments:
        timestamp = format_timestamp(segment.start)
        rows.append(f"**[{timestamp}]** {segment.text.strip()}")
    return "\n\n".join(rows).strip() + "\n"


def _vtt_timestamp(seconds: float) -> str:
    milliseconds = max(0, round(seconds * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1_000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


def _vtt(transcript: Transcript) -> str:
    rows = ["WEBVTT", ""]
    for index, segment in enumerate(transcript.segments, start=1):
        end = segment.end if segment.end > segment.start else segment.start + 1
        rows.extend(
            [
                str(index),
                f"{_vtt_timestamp(segment.start)} --> {_vtt_timestamp(end)}",
                segment.text.strip(),
                "",
            ]
        )
    return "\n".join(rows)


def _paragraphs(text: str) -> str:
    return "\n".join(
        f"<p>{html.escape(part.strip())}</p>"
        for part in re.split(r"\n+", text)
        if part.strip()
    )


def _page_html(
    site_title: str,
    item: DiscoveredItem,
    title_zh: str,
    chinese: Transcript,
    original: Transcript,
) -> str:
    chinese_html = _paragraphs(chinese.text)
    original_html = _paragraphs(original.text)
    published = item.published_at.astimezone(timezone.utc).strftime("%Y-%m-%d")
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title_zh)} · {html.escape(site_title)}</title>
  <style>
    :root {{ color-scheme: light dark; font-family: system-ui, sans-serif; }}
    body {{ margin: 0; line-height: 1.75; }}
    header, main, footer {{ width: min(780px, calc(100% - 32px)); margin: 0 auto; }}
    header {{ padding: 40px 0 20px; border-bottom: 1px solid #8885; }}
    main {{ padding: 24px 0 48px; }}
    h1 {{ font-size: 1.8rem; line-height: 1.3; letter-spacing: 0; }}
    h2 {{ margin-top: 2.5rem; font-size: 1.2rem; letter-spacing: 0; }}
    p {{ margin: 0 0 1rem; }}
    .meta {{ color: #777; }}
    a {{ color: #0969da; }}
    details {{ margin-top: 3rem; border-top: 1px solid #8885; padding-top: 1rem; }}
    summary {{ cursor: pointer; font-weight: 600; }}
    footer {{ padding: 20px 0 40px; color: #777; font-size: .9rem; }}
  </style>
</head>
<body>
  <header>
    <p><a href="../../index.html">{html.escape(site_title)}</a></p>
    <h1>{html.escape(title_zh)}</h1>
    <p class="meta">{published} · {html.escape(chinese.provenance)}</p>
    <p><a href="{html.escape(item.url)}">打开原始节目</a></p>
  </header>
  <main>
    <p><strong>自动处理提示：</strong>文字识别和机器翻译可能有误，重要内容请核对原始音视频。</p>
    <h2>中文文字稿</h2>
    {chinese_html}
    <details>
      <summary>查看原文</summary>
      <h2>{html.escape(item.title)}</h2>
      {original_html}
    </details>
  </main>
  <footer>{html.escape(site_title)}</footer>
</body>
</html>
"""


def write_item(
    config: AppConfig,
    item: DiscoveredItem,
    title_zh: str,
    original: Transcript,
    chinese: Transcript,
) -> dict[str, Any]:
    slug = stable_item_slug(item.source_id, item.external_id)
    item_dir = config.site.output_dir / "items" / slug
    item_dir.mkdir(parents=True, exist_ok=True)
    (item_dir / "original.md").write_text(_markdown(original), encoding="utf-8")
    (item_dir / "zh.md").write_text(_markdown(chinese), encoding="utf-8")
    (item_dir / "original.vtt").write_text(_vtt(original), encoding="utf-8")
    (item_dir / "zh.vtt").write_text(_vtt(chinese), encoding="utf-8")
    (item_dir / "zh.txt").write_text(chinese.text.strip() + "\n", encoding="utf-8")
    (item_dir / "index.html").write_text(
        _page_html(config.site.title, item, title_zh, chinese, original),
        encoding="utf-8",
    )
    return {
        **item.as_state_dict(),
        "status": "published",
        "title_zh": title_zh,
        "language": original.language,
        "transcript_provenance": original.provenance,
        "translation_provenance": chinese.provenance,
        "item_slug": slug,
        "published_to_feed_at": datetime.now(timezone.utc).isoformat(),
    }


def _load_item_text(output_dir: Path, row: dict[str, Any]) -> str:
    path = output_dir / "items" / row["item_slug"] / "zh.txt"
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()


def _item_url(config: AppConfig, row: dict[str, Any]) -> str:
    return f"{config.site.base_url}/items/{row['item_slug']}/"


def _feed_xml(
    config: AppConfig,
    title: str,
    description: str,
    feed_url: str,
    rows: list[dict[str, Any]],
) -> bytes:
    rss = ElementTree.Element("rss", {"version": "2.0"})
    channel = ElementTree.SubElement(rss, "channel")
    ElementTree.SubElement(channel, "title").text = title
    ElementTree.SubElement(channel, "link").text = config.site.base_url
    ElementTree.SubElement(channel, "description").text = description
    ElementTree.SubElement(channel, "language").text = "zh-CN"
    ElementTree.SubElement(
        channel,
        f"{{{ATOM_NS}}}link",
        {"href": feed_url, "rel": "self", "type": "application/rss+xml"},
    )

    for row in rows[: config.site.feed_items]:
        text = _load_item_text(config.site.output_dir, row)
        if not text:
            continue
        page_url = _item_url(config, row)
        node = ElementTree.SubElement(channel, "item")
        ElementTree.SubElement(node, "title").text = row["title_zh"]
        ElementTree.SubElement(node, "link").text = page_url
        ElementTree.SubElement(node, "guid", {"isPermaLink": "false"}).text = (
            f"{row['source_id']}:{row['external_id']}"
        )
        published = datetime.fromisoformat(row["published_at"])
        if published.tzinfo is None:
            published = published.replace(tzinfo=timezone.utc)
        ElementTree.SubElement(node, "pubDate").text = format_datetime(published)
        summary = text[:1_200] + ("…" if len(text) > 1_200 else "")
        ElementTree.SubElement(node, "description").text = summary

        if config.site.content_mode == "full":
            content = text[: config.site.content_max_characters]
            if len(text) > len(content):
                content += f"\n\n全文：{page_url}"
        elif config.site.content_mode == "summary":
            content = summary
        else:
            content = ""
        if content:
            ElementTree.SubElement(node, f"{{{CONTENT_NS}}}encoded").text = _paragraphs(content)
        ElementTree.SubElement(
            node,
            f"{{{PODCAST_NS}}}transcript",
            {
                "url": f"{page_url}zh.vtt",
                "type": "text/vtt",
                "language": "zh-CN",
                "rel": "captions",
            },
        )
        ElementTree.SubElement(node, "source", {"url": row["url"]}).text = row["source_id"]
    return ElementTree.tostring(rss, encoding="utf-8", xml_declaration=True)


def _index_html(config: AppConfig, rows: list[dict[str, Any]]) -> str:
    items = []
    for row in rows:
        date = datetime.fromisoformat(row["published_at"]).strftime("%Y-%m-%d")
        items.append(
            "<li>"
            f"<time>{html.escape(date)}</time> "
            f"<a href=\"items/{html.escape(row['item_slug'])}/\">"
            f"{html.escape(row['title_zh'])}</a>"
            f"<small>{html.escape(row['source_id'])}</small>"
            "</li>"
        )
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(config.site.title)}</title>
  <link rel="alternate" type="application/rss+xml" href="feed.xml">
  <style>
    :root {{ color-scheme: light dark; font-family: system-ui, sans-serif; }}
    body {{ margin: 0; line-height: 1.6; }}
    main {{ width: min(860px, calc(100% - 32px)); margin: 0 auto; padding: 48px 0; }}
    h1 {{ font-size: 2rem; letter-spacing: 0; }}
    ul {{ list-style: none; padding: 0; border-top: 1px solid #8885; }}
    li {{ display: grid; grid-template-columns: 7rem 1fr auto; gap: 12px; padding: 14px 0; border-bottom: 1px solid #8885; }}
    time, small {{ color: #777; }}
    a {{ color: #0969da; }}
    @media (max-width: 600px) {{ li {{ grid-template-columns: 1fr; gap: 2px; }} }}
  </style>
</head>
<body>
  <main>
    <h1>{html.escape(config.site.title)}</h1>
    <p>{html.escape(config.site.description)}</p>
    <p><a href="feed.xml">订阅全部文字稿 RSS</a></p>
    <ul>{''.join(items)}</ul>
  </main>
</body>
</html>
"""


def rebuild_site(
    config: AppConfig,
    sources: list[SourceConfig],
    state: dict[str, Any],
) -> None:
    output = config.site.output_dir
    (output / "feeds").mkdir(parents=True, exist_ok=True)
    (output / ".nojekyll").touch()
    published = [
        row
        for row in state.get("items", {}).values()
        if row.get("status") == "published" and row.get("item_slug")
    ]
    published.sort(key=lambda row: row["published_at"], reverse=True)
    (output / "feed.xml").write_bytes(
        _feed_xml(
            config,
            config.site.title,
            config.site.description,
            f"{config.site.base_url}/feed.xml",
            published,
        )
    )
    for source in sources:
        rows = [row for row in published if row.get("source_id") == source.id]
        source_title = source.title or state.get("sources", {}).get(source.id, {}).get("title") or source.id
        feed_path = output / "feeds" / f"{source.id}.xml"
        feed_path.write_bytes(
            _feed_xml(
                config,
                f"{source_title} 中文文字稿",
                f"{source_title} 的自动生成中文文字稿",
                f"{config.site.base_url}/feeds/{source.id}.xml",
                rows,
            )
        )
    (output / "index.html").write_text(_index_html(config, published), encoding="utf-8")
