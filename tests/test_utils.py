from transcript_rss.utils import parse_datetime, to_simplified


def test_parse_unix_timestamp() -> None:
    result = parse_datetime("1785114000")

    assert result.isoformat() == "2026-07-27T01:00:00+00:00"


def test_to_simplified_converts_traditional_characters() -> None:
    assert to_simplified("這是繁體中文") == "这是繁体中文"


def test_to_simplified_leaves_simplified_text_unchanged() -> None:
    assert to_simplified("这已经是简体中文了") == "这已经是简体中文了"
