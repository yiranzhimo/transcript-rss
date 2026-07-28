import httpx

from transcript_rss.models import Segment, Transcript, TranslationConfig
from transcript_rss.translate import OpenAICompatibleTranslator, build_translation_chunks


def test_translation_chunks_keep_timestamps() -> None:
    transcript = Transcript(
        "en",
        [
            Segment(1, 2, "First sentence."),
            Segment(65, 67, "Second sentence."),
        ],
        "test",
    )

    chunks = build_translation_chunks(transcript, 500)

    assert "[00:00:01]" in chunks[0].text
    assert "[00:01:05]" in chunks[0].text


def test_openai_compatible_translation(monkeypatch) -> None:
    monkeypatch.setenv("TEST_TRANSLATION_KEY", "secret")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer secret"
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "[00:00:01] 你好。"}}]},
        )

    config = TranslationConfig(
        api_base="https://translator.example/v1",
        model="test-model",
        api_key_env="TEST_TRANSLATION_KEY",
    )
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        translator = OpenAICompatibleTranslator(config, client)
        result = translator.translate_transcript(
            Transcript("en", [Segment(1, 2, "Hello.")], "test")
        )

    assert result.language == "zh-CN"
    assert "你好" in result.text
    assert result.text.startswith("你好")
    assert result.segments[0].start == 1
