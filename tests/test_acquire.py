import json

from transcript_rss.acquire import parse_transcript


def test_parses_json3_events() -> None:
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
