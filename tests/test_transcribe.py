import sys
from types import SimpleNamespace

from transcript_rss.models import TranscriptionConfig
from transcript_rss.transcribe import WhisperTranscriber


class _Row:
    start = 1.25
    end = 2.75
    text = "  测试文字  "


class _Info:
    language = "zh"


def test_transcriber_uses_batched_inference(tmp_path, monkeypatch) -> None:
    calls = {}

    class FakeModel:
        def __init__(self, model, **options):
            calls["model_init"] = (model, options)

        def transcribe(self, *args, **kwargs):
            raise AssertionError("standard transcription should not be used")

    class FakeBatchedPipeline:
        def __init__(self, model):
            calls["batch_model"] = model

        def transcribe(self, audio, **options):
            calls["batch_transcribe"] = (audio, options)
            return iter([_Row()]), _Info()

    monkeypatch.setitem(
        sys.modules,
        "faster_whisper",
        SimpleNamespace(
            WhisperModel=FakeModel,
            BatchedInferencePipeline=FakeBatchedPipeline,
        ),
    )
    transcriber = WhisperTranscriber(
        TranscriptionConfig(
            batch_size=8,
            beam_size=1,
            cpu_threads=4,
            log_progress=True,
        )
    )

    transcript = transcriber.transcribe(tmp_path / "audio.mp3", "zh-CN")

    assert calls["model_init"] == (
        "small",
        {"device": "cpu", "compute_type": "int8", "cpu_threads": 4},
    )
    assert calls["batch_transcribe"][1] == {
        "batch_size": 8,
        "language": "zh",
        "vad_filter": True,
        "beam_size": 1,
        "log_progress": True,
    }
    assert transcript.language == "zh"
    assert transcript.segments[0].text == "测试文字"
    assert transcript.provenance == "faster-whisper/small; batch=8; beam=1"


def test_transcriber_falls_back_when_batching_is_unavailable(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    calls = {}

    class FakeModel:
        def __init__(self, model, **options):
            calls["model_init"] = (model, options)

        def transcribe(self, audio, **options):
            calls["transcribe"] = (audio, options)
            return iter([_Row()]), _Info()

    monkeypatch.setitem(
        sys.modules,
        "faster_whisper",
        SimpleNamespace(WhisperModel=FakeModel),
    )
    transcriber = WhisperTranscriber(TranscriptionConfig(batch_size=8))

    transcript = transcriber.transcribe(tmp_path / "audio.mp3", "auto")

    assert calls["transcribe"][1]["language"] is None
    assert transcript.provenance == "faster-whisper/small; batch=0; beam=1"
    assert "does not support batched inference" in capsys.readouterr().out
