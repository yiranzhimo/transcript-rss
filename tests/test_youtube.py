from pathlib import Path

import pytest

from transcript_rss.youtube import youtube_options


def test_youtube_options_enable_javascript_runtimes(monkeypatch) -> None:
    monkeypatch.delenv("YOUTUBE_COOKIES_FILE", raising=False)
    monkeypatch.delenv("YOUTUBE_PROXY", raising=False)
    monkeypatch.delenv("YOUTUBE_POT_PROVIDER_URL", raising=False)

    options = youtube_options(skip_download=True)

    assert options["js_runtimes"] == {"deno": {}, "node": {}}
    assert options["skip_download"] is True


def test_youtube_options_include_optional_network_configuration(
    tmp_path: Path,
    monkeypatch,
) -> None:
    cookies = tmp_path / "cookies.txt"
    cookies.write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")
    monkeypatch.setenv("YOUTUBE_COOKIES_FILE", str(cookies))
    monkeypatch.setenv("YOUTUBE_PROXY", "http://proxy.example:8080")
    monkeypatch.setenv("YOUTUBE_POT_PROVIDER_URL", "http://127.0.0.1:4416/")

    options = youtube_options()

    assert options["cookiefile"] == str(cookies)
    assert options["proxy"] == "http://proxy.example:8080"
    assert options["extractor_args"]["youtubepot-bgutilhttp"]["base_url"] == [
        "http://127.0.0.1:4416"
    ]


def test_youtube_options_reject_missing_cookie_file(monkeypatch) -> None:
    monkeypatch.setenv("YOUTUBE_COOKIES_FILE", "/missing/cookies.txt")

    with pytest.raises(FileNotFoundError):
        youtube_options()
