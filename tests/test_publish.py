from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree

from transcript_rss.models import (
    AppConfig,
    DiscoveredItem,
    Segment,
    SiteConfig,
    SourceConfig,
    Transcript,
    TranscriptionConfig,
    TranslationConfig,
)
from transcript_rss.publish import CONTENT_NS, PODCAST_NS, rebuild_site, write_item


def test_writes_full_text_feed_and_transcript_link(tmp_path: Path) -> None:
    output = tmp_path / "docs"
    source = SourceConfig(id="show", type="podcast", url="https://example.com/feed.xml")
    config = AppConfig(
        site=SiteConfig(
            title="文字稿",
            description="测试",
            base_url="https://owner.github.io/transcript-rss",
            output_dir=output,
            state_file=tmp_path / "data/state.json",
        ),
        translation=TranslationConfig(),
        transcription=TranscriptionConfig(),
        sources=[source],
        config_path=tmp_path / "config.yaml",
    )
    item = DiscoveredItem(
        source_id="show",
        source_type="podcast",
        external_id="episode-1",
        title="Episode One",
        url="https://example.com/episodes/1",
        published_at=datetime(2026, 7, 27, tzinfo=timezone.utc),
    )
    original = Transcript("en", [Segment(0, 3, "Hello world")], "publisher")
    chinese = Transcript("zh-CN", [Segment(0, 3, "你好，世界")], "translation/test")
    row = write_item(config, item, "第一期", original, chinese)
    state = {
        "version": 1,
        "sources": {"show": {"title": "Example Show"}},
        "items": {"show/episode-1": row},
    }

    rebuild_site(config, [source], state)

    root = ElementTree.parse(output / "feed.xml").getroot()
    item_node = root.find("./channel/item")
    assert item_node is not None
    assert "你好，世界" in (item_node.find(f"{{{CONTENT_NS}}}encoded").text or "")
    transcript = item_node.find(f"{{{PODCAST_NS}}}transcript")
    assert transcript is not None
    assert transcript.attrib["url"].endswith("/zh.vtt")
    assert (output / "items" / row["item_slug"] / "original.md").exists()
    assert item_node.find("link").text == f"https://owner.github.io/transcript-rss/items/{row['item_slug']}/"


def test_youtube_feed_item_links_directly_to_the_video(tmp_path: Path) -> None:
    output = tmp_path / "docs"
    source = SourceConfig(id="channel", type="youtube", url="https://www.youtube.com/feeds/videos.xml?channel_id=UC1")
    config = AppConfig(
        site=SiteConfig(
            title="文字稿",
            description="测试",
            base_url="https://owner.github.io/transcript-rss",
            output_dir=output,
            state_file=tmp_path / "data/state.json",
        ),
        translation=TranslationConfig(),
        transcription=TranscriptionConfig(),
        sources=[source],
        config_path=tmp_path / "config.yaml",
    )
    item = DiscoveredItem(
        source_id="channel",
        source_type="youtube",
        external_id="youtube:abc123",
        title="A great video",
        url="https://www.youtube.com/watch?v=abc123",
        published_at=datetime(2026, 7, 27, tzinfo=timezone.utc),
    )
    transcript = Transcript("zh-CN", [Segment(0, 0, "简介文本")], "video title/description only")
    row = write_item(config, item, "一个很棒的视频", transcript, transcript)
    state = {
        "version": 1,
        "sources": {"channel": {"title": "Example Channel"}},
        "items": {"channel/youtube:abc123": row},
    }

    rebuild_site(config, [source], state)

    root = ElementTree.parse(output / "feed.xml").getroot()
    item_node = root.find("./channel/item")
    assert item_node is not None
    assert item_node.find("link").text == "https://www.youtube.com/watch?v=abc123"

    index_html = (output / "index.html").read_text(encoding="utf-8")
    assert 'href="https://www.youtube.com/watch?v=abc123"' in index_html
