from transcript_rss.utils import parse_datetime


def test_parse_unix_timestamp() -> None:
    result = parse_datetime("1785114000")

    assert result.isoformat() == "2026-07-27T01:00:00+00:00"
