from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass

import httpx

from .models import Segment, Transcript, TranslationConfig
from .utils import format_timestamp


def _split_text(text: str, limit: int) -> list[str]:
    text = " ".join(text.split())
    if len(text) <= limit:
        return [text]
    sentences = re.split(r"(?<=[.!?。！？])\s+", text)
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        if len(sentence) > limit:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(sentence[index : index + limit] for index in range(0, len(sentence), limit))
        elif not current:
            current = sentence
        elif len(current) + len(sentence) + 1 <= limit:
            current = f"{current} {sentence}"
        else:
            chunks.append(current)
            current = sentence
    if current:
        chunks.append(current)
    return chunks


@dataclass(slots=True)
class TranslationChunk:
    start: float
    end: float
    text: str


def build_translation_chunks(transcript: Transcript, character_limit: int) -> list[TranslationChunk]:
    chunks: list[TranslationChunk] = []
    current_lines: list[str] = []
    current_start = 0.0
    current_end = 0.0
    current_size = 0

    def flush() -> None:
        nonlocal current_lines, current_start, current_end, current_size
        if current_lines:
            chunks.append(
                TranslationChunk(
                    start=current_start,
                    end=current_end,
                    text="\n".join(current_lines),
                )
            )
        current_lines = []
        current_start = 0.0
        current_end = 0.0
        current_size = 0

    for segment in transcript.segments:
        pieces = _split_text(segment.text, max(200, character_limit - 20))
        for piece in pieces:
            line = f"[{format_timestamp(segment.start)}] {piece}"
            if current_lines and current_size + len(line) + 1 > character_limit:
                flush()
            if not current_lines:
                current_start = segment.start
            current_lines.append(line)
            current_end = max(segment.end, segment.start)
            current_size += len(line) + 1
    flush()
    return chunks


class OpenAICompatibleTranslator:
    def __init__(self, config: TranslationConfig, client: httpx.Client):
        self.config = config
        self.client = client

    @property
    def api_key(self) -> str:
        value = os.getenv(self.config.api_key_env, "").strip()
        if not value:
            raise RuntimeError(
                f"translation requires the {self.config.api_key_env} environment variable"
            )
        return value

    def _request(self, system: str, text: str) -> str:
        response: httpx.Response | None = None
        for attempt in range(3):
            response = self.client.post(
                f"{self.config.api_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.config.model,
                    "temperature": 0,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": text},
                    ],
                },
                timeout=120,
            )
            if response.status_code < 500 and response.status_code != 429:
                break
            time.sleep(2**attempt)
        assert response is not None
        response.raise_for_status()
        payload = response.json()
        result = payload["choices"][0]["message"]["content"].strip()
        if result.startswith("```") and result.endswith("```"):
            result = re.sub(r"^```[a-zA-Z]*\s*", "", result)
            result = re.sub(r"\s*```$", "", result)
        if not result:
            raise ValueError("translation API returned empty content")
        return result.strip()

    def translate_title(self, title: str) -> str:
        return self._request(
            "Translate the supplied English title into concise Simplified Chinese. "
            "Preserve names, numbers, and meaning. Return only the translated title.",
            title,
        ).replace("\n", " ")

    def translate_transcript(self, transcript: Transcript) -> Transcript:
        chunks = build_translation_chunks(transcript, self.config.chunk_characters)
        translated: list[Segment] = []
        system = (
            "Translate this English transcript faithfully into natural Simplified Chinese. "
            "Do not summarize, omit, add facts, or add commentary. Keep every [HH:MM:SS] "
            "timestamp exactly where it appears. Keep proper nouns in their conventional "
            "Chinese form and include the original spelling when ambiguity would result. "
            "Return only the translated transcript."
        )
        for chunk in chunks:
            text = self._request(system, chunk.text)
            translated.extend(_parse_translated_chunk(text, chunk))
        return Transcript(
            language="zh-CN",
            segments=translated,
            provenance=f"translation/{self.config.model} from {transcript.provenance}",
        )


TRANSLATED_TIMESTAMP_RE = re.compile(r"^\[(\d{2}):(\d{2}):(\d{2})\]\s*(.*)$")


def _parse_translated_chunk(text: str, chunk: TranslationChunk) -> list[Segment]:
    rows: list[tuple[float, str]] = []
    for line in text.splitlines():
        match = TRANSLATED_TIMESTAMP_RE.match(line.strip())
        if match:
            hours, minutes, seconds, content = match.groups()
            start = int(hours) * 3600 + int(minutes) * 60 + int(seconds)
            rows.append((float(start), content.strip()))
        elif line.strip() and rows:
            start, previous = rows[-1]
            rows[-1] = (start, f"{previous} {line.strip()}".strip())

    if not rows:
        return [
            Segment(
                start=chunk.start,
                end=max(chunk.end, chunk.start + 1),
                text=text.strip(),
            )
        ]

    segments: list[Segment] = []
    for index, (start, content) in enumerate(rows):
        if not content:
            continue
        next_start = rows[index + 1][0] if index + 1 < len(rows) else chunk.end
        end = next_start if next_start > start else start + 1
        segments.append(Segment(start=start, end=end, text=content))
    return segments
