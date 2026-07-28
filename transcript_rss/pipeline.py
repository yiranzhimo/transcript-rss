from __future__ import annotations

import shutil
import tempfile
import traceback
from pathlib import Path
from typing import Any

import httpx

from .acquire import (
    download_podcast_audio,
    download_youtube_audio,
    fetch_existing_transcript,
)
from .artifacts import write_source_artifact
from .discover import discover_source
from .models import AppConfig, DiscoveredItem, SourceConfig, Transcript
from .publish import rebuild_site, write_item
from .state import load_state, save_state
from .transcribe import WhisperTranscriber
from .translate import OpenAICompatibleTranslator
from .utils import detect_text_language, is_english, normalize_language, utc_now


def _state_key(item: DiscoveredItem) -> str:
    return f"{item.source_id}::{item.external_id}"


def _resolved_language(source: SourceConfig, transcript: Transcript) -> str:
    transcript_language = normalize_language(transcript.language)
    if transcript_language != "und":
        return transcript_language
    configured = normalize_language(source.language)
    if configured not in {"auto", "und"}:
        return configured
    return detect_text_language(transcript.text)


def _download_and_transcribe(
    config: AppConfig,
    source: SourceConfig,
    item: DiscoveredItem,
    client: httpx.Client,
    work_dir: Path,
    transcriber: WhisperTranscriber,
) -> Transcript:
    if not config.transcription.enabled:
        raise RuntimeError("no usable transcript and audio transcription is disabled")
    if source.type == "podcast":
        audio_path = download_podcast_audio(
            item,
            client,
            work_dir,
            config.transcription.max_download_mb,
        )
    else:
        audio_path = download_youtube_audio(item, work_dir)
    return transcriber.transcribe(audio_path, source.language)


def _record_failure(
    state: dict[str, Any],
    item: DiscoveredItem,
    error: Exception,
) -> None:
    key = _state_key(item)
    previous = state["items"].get(key, {})
    state["items"][key] = {
        **item.as_state_dict(),
        "status": "failed",
        "attempts": int(previous.get("attempts", 0)) + 1,
        "last_error": f"{type(error).__name__}: {error}",
        "last_attempt_at": utc_now().isoformat(),
    }
    state["sources"].setdefault(item.source_id, {})["force_refresh"] = True


def run_sync(
    config: AppConfig,
    fail_on_error: bool = False,
    artifact_dir: Path | None = None,
) -> dict[str, int]:
    state = load_state(config.site.state_file)
    state.setdefault("sources", {})
    state.setdefault("items", {})
    stats = {"discovered": 0, "published": 0, "failed": 0, "skipped": 0}
    client = httpx.Client(
        follow_redirects=True,
        timeout=httpx.Timeout(60, connect=20),
        headers={"User-Agent": "transcript-rss/0.1 (+personal feed reader)"},
    )
    translator = OpenAICompatibleTranslator(config.translation, client)
    transcriber = WhisperTranscriber(config.transcription)
    published_slugs: set[str] = set()

    try:
        for source in config.sources:
            if not source.enabled:
                continue
            source_state = state["sources"].setdefault(source.id, {})
            source_state.update({"type": source.type, "url": source.url})
            print(f"[discover] {source.id}")
            try:
                discovered = discover_source(source, client, source_state)
                source_state["force_refresh"] = False
            except Exception as error:
                stats["failed"] += 1
                source_state["force_refresh"] = True
                source_state["last_error"] = f"{type(error).__name__}: {error}"
                source_state["last_attempt_at"] = utc_now().isoformat()
                print(f"[error] {source.id}: {error}")
                if fail_on_error:
                    raise
                continue

            stats["discovered"] += len(discovered)
            if discovered:
                detected_title = (
                    discovered[0].metadata.get("feed_title")
                    or discovered[0].metadata.get("channel_title")
                )
                source_state["title"] = source.title or detected_title or source.id

            pending = [
                item
                for item in discovered
                if state["items"].get(_state_key(item), {}).get("status") != "published"
            ]
            pending.sort(
                key=lambda item: (
                    int(state["items"].get(_state_key(item), {}).get("attempts", 0)),
                    -item.published_at.timestamp(),
                )
            )
            selected = pending[: source.max_items_per_run]
            stats["skipped"] += max(0, len(pending) - len(selected))
            source_state["force_refresh"] = len(pending) > len(selected)

            for item in reversed(selected):
                print(f"[process] {source.id}: {item.title}")
                try:
                    with tempfile.TemporaryDirectory(prefix="transcript-rss-") as temp:
                        work_dir = Path(temp)
                        transcript, _ = fetch_existing_transcript(source, item, client)
                        if transcript is None:
                            transcript = _download_and_transcribe(
                                config,
                                source,
                                item,
                                client,
                                work_dir,
                                transcriber,
                            )
                        transcript.language = _resolved_language(source, transcript)

                        if is_english(transcript.language):
                            if not config.translation.enabled:
                                raise RuntimeError(
                                    "English transcript found but translation is disabled"
                                )
                            chinese = translator.translate_transcript(transcript)
                            title_zh = translator.translate_title(item.title)
                        else:
                            chinese = transcript
                            title_zh = item.title

                        row = write_item(config, item, title_zh, transcript, chinese)
                        row["attempts"] = (
                            int(state["items"].get(_state_key(item), {}).get("attempts", 0)) + 1
                        )
                        state["items"][_state_key(item)] = row
                        published_slugs.add(row["item_slug"])
                        source_state.pop("last_error", None)
                        stats["published"] += 1
                        print(f"[published] {title_zh}")
                except Exception as error:
                    stats["failed"] += 1
                    _record_failure(state, item, error)
                    print(f"[error] {source.id}/{item.external_id}: {error}")
                    if fail_on_error:
                        traceback.print_exc()
                        raise
                finally:
                    save_state(config.site.state_file, state)

        if artifact_dir is None:
            rebuild_site(config, config.sources, state)
        save_state(config.site.state_file, state)
        if artifact_dir is not None:
            write_source_artifact(config, state, published_slugs, artifact_dir)
    finally:
        client.close()
        work_root = config.config_path.parent / "work"
        if work_root.exists():
            shutil.rmtree(work_root, ignore_errors=True)
    return stats
