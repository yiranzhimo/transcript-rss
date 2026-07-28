from __future__ import annotations

from pathlib import Path

from .models import Segment, Transcript, TranscriptionConfig
from .utils import normalize_language


class WhisperTranscriber:
    def __init__(self, config: TranscriptionConfig):
        self.config = config
        self._model = None

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
            )
        return self._model

    def transcribe(self, audio_path: Path, language: str = "auto") -> Transcript:
        model = self._load_model()
        requested_language = None if language in {"", "auto", "und"} else language.split("-", 1)[0]
        rows, info = model.transcribe(
            str(audio_path),
            language=requested_language,
            vad_filter=True,
            beam_size=5,
        )
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
            provenance=f"faster-whisper/{self.config.model}",
        )
