import json
from datetime import datetime, timezone

from transcript_rss.acquire import build_video_summary_transcript, parse_transcript
from transcript_rss.models import DiscoveredItem


def test_parses_youtube_json3() -> None:
    payload = {
        "events": [
            {
                "tStartMs": 1000,
                "dDurationMs": 2500,
                "segs": [{"utf8": "Hello "}, {"utf8": "world"}],
            }
        ]
    }

    transcript = parse_transcript(
        json.dumps(payload).encode(),
        "application/json",
        "https://example.com/captions.json",
        "en",
        "test",
    )

    assert transcript.language == "en"
    assert transcript.segments[0].start == 1
    assert transcript.segments[0].end == 3.5
    assert transcript.text == "Hello world"


def test_parses_vtt() -> None:
    transcript = parse_transcript(
        b"WEBVTT\n\n00:00:01.000 --> 00:00:03.000\nHello world\n",
        "text/vtt",
        "https://example.com/captions.vtt",
        None,
        "test",
    )

    assert transcript.language == "en"
    assert transcript.segments[0].text == "Hello world"


def _item(**overrides) -> DiscoveredItem:
    defaults = dict(
        source_id="some-channel",
        source_type="youtube",
        external_id="youtube:abc123",
        title="A great video",
        url="https://www.youtube.com/watch?v=abc123",
        published_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        description="",
    )
    defaults.update(overrides)
    return DiscoveredItem(**defaults)


def test_build_video_summary_transcript_uses_description() -> None:
    item = _item(description="This video explains things.\n\nIn two paragraphs.")

    transcript = build_video_summary_transcript(item)

    assert transcript.provenance == "video title/description only (no transcript fetched)"
    assert [segment.text for segment in transcript.segments] == [
        "This video explains things.",
        "In two paragraphs.",
    ]


def test_build_video_summary_transcript_falls_back_to_title() -> None:
    item = _item(description="   ", title="A great video")

    transcript = build_video_summary_transcript(item)

    assert transcript.text == "A great video"
