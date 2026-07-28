from __future__ import annotations

from pathlib import Path

from .models import Segment, Transcript, TranscriptionConfig
from .utils import normalize_language


class WhisperTranscriber:
    def __init__(self, config: TranscriptionConfig):
        self.config = config
        self._model = None
        self._batched_model = None
        self._batch_unavailable = False

    def _load_model(self):
        if self._model is None:
            try:
                from faster_whisper import WhisperModel
            except ImportError as exc:
                raise RuntimeError(
                    "faster-whisper is required for audio transcription; "
                    "install the project with the transcribe extra"
                ) from exc
            self._model = WhisperModel(
                self.config.model,
                device=self.config.device,
                compute_type=self.config.compute_type,
                cpu_threads=self.config.cpu_threads,
            )
        return self._model

    def _load_batched_model(self):
        if self.config.batch_size <= 0 or self._batch_unavailable:
            return None
        if self._batched_model is None:
            try:
                from faster_whisper import BatchedInferencePipeline
            except ImportError:
                self._batch_unavailable = True
                print(
                    "[warn] installed faster-whisper does not support batched inference; "
                    "using standard transcription",
                    flush=True,
                )
                return None
            self._batched_model = BatchedInferencePipeline(model=self._load_model())
        return self._batched_model

    def transcribe(self, audio_path: Path, language: str = "auto") -> Transcript:
        model = self._load_model()
        requested_language = None if language in {"", "auto", "und"} else language.split("-", 1)[0]
        batched_model = self._load_batched_model()
        options = {
            "language": requested_language,
            "vad_filter": True,
            "beam_size": self.config.beam_size,
            "log_progress": self.config.log_progress,
        }
        if batched_model is not None:
            rows, info = batched_model.transcribe(
                str(audio_path),
                batch_size=self.config.batch_size,
                **options,
            )
        else:
            rows, info = model.transcribe(str(audio_path), **options)
        segments = [
            Segment(start=float(row.start), end=float(row.end), text=row.text.strip())
            for row in rows
            if row.text.strip()
        ]
        if not segments:
            raise ValueError("Whisper returned an empty transcript")
        detected_language = normalize_language(getattr(info, "language", requested_language))
        return Transcript(
            language=detected_language,
            segments=segments,
            provenance=(
                f"faster-whisper/{self.config.model}; "
                f"batch={self.config.batch_size if batched_model is not None else 0}; "
                f"beam={self.config.beam_size}"
            ),
        )
