import json
from pathlib import Path

from transcript_rss.artifacts import merge_source_artifacts, write_source_artifact
from transcript_rss.models import (
    AppConfig,
    SiteConfig,
    SourceConfig,
    TranscriptionConfig,
    TranslationConfig,
)


def _config(
    tmp_path: Path,
    sources: list[SourceConfig],
    *,
    name: str,
) -> AppConfig:
    root = tmp_path / name
    return AppConfig(
        site=SiteConfig(
            title="文字稿",
            description="测试",
            base_url="https://owner.github.io/transcript-rss",
            output_dir=root / "docs",
            state_file=root / "data/state.json",
        ),
        translation=TranslationConfig(),
        transcription=TranscriptionConfig(),
        sources=sources,
        config_path=root / "config.yaml",
    )


def _published_row(source_id: str, slug: str) -> dict[str, str]:
    return {
        "source_id": source_id,
        "source_type": "podcast",
        "external_id": f"{source_id}-episode",
        "title": "Episode",
        "title_zh": "节目",
        "url": "https://example.com/episode",
        "published_at": "2026-07-28T00:00:00+00:00",
        "status": "published",
        "item_slug": slug,
    }


def test_source_artifacts_merge_without_overwriting_other_sources(tmp_path: Path) -> None:
    source_a = SourceConfig(id="source-a", type="podcast", url="https://example.com/a")
    source_b = SourceConfig(id="source-b", type="podcast", url="https://example.com/b")
    artifacts = tmp_path / "artifacts"

    worker_a = _config(tmp_path, [source_a], name="worker-a")
    slug = "source-a-123456789abc"
    item_dir = worker_a.site.output_dir / "items" / slug
    item_dir.mkdir(parents=True)
    (item_dir / "zh.txt").write_text("并行生成的文字稿\n", encoding="utf-8")
    state_a = {
        "version": 1,
        "sources": {
            "source-a": {"title": "来源 A", "force_refresh": False},
            "source-b": {"title": "不应由来源 A 覆盖"},
        },
        "items": {
            "source-a::episode": _published_row("source-a", slug),
            "source-b::stale": _published_row("source-b", "stale"),
        },
    }
    write_source_artifact(worker_a, state_a, [slug], artifacts / "source-source-a")

    worker_b = _config(tmp_path, [source_b], name="worker-b")
    state_b = {
        "version": 1,
        "sources": {
            "source-b": {
                "title": "来源 B",
                "force_refresh": True,
                "last_error": "HTTPError: unavailable",
            }
        },
        "items": {},
    }
    write_source_artifact(worker_b, state_b, [], artifacts / "source-source-b")

    merged = _config(tmp_path, [source_a, source_b], name="merged")
    result = merge_source_artifacts(merged, artifacts)
    state = json.loads(merged.site.state_file.read_text(encoding="utf-8"))

    assert result == {
        "artifacts": 2,
        "sources": 2,
        "items": 1,
        "missing_sources": [],
    }
    assert set(state["sources"]) == {"source-a", "source-b"}
    assert state["sources"]["source-b"]["title"] == "来源 B"
    assert state["sources"]["source-b"]["last_error"] == "HTTPError: unavailable"
    assert state["items"]["source-a::episode"]["status"] == "published"
    assert "source-b::stale" not in state["items"]
    assert (
        merged.site.output_dir / "items" / slug / "zh.txt"
    ).read_text(encoding="utf-8") == "并行生成的文字稿\n"
    assert (merged.site.output_dir / "feed.xml").exists()
    assert (merged.site.output_dir / "feeds" / "source-a.xml").exists()
    assert (merged.site.output_dir / "feeds" / "source-b.xml").exists()


def test_merge_reports_missing_source_artifacts(tmp_path: Path, capsys) -> None:
    source_a = SourceConfig(id="source-a", type="podcast", url="https://example.com/a")
    source_b = SourceConfig(id="source-b", type="podcast", url="https://example.com/b")
    artifacts = tmp_path / "artifacts"
    worker = _config(tmp_path, [source_a], name="worker")
    state = {
        "version": 1,
        "sources": {"source-a": {"title": "来源 A"}},
        "items": {},
    }
    write_source_artifact(worker, state, [], artifacts / "source-source-a")

    merged = _config(tmp_path, [source_a, source_b], name="merged")
    result = merge_source_artifacts(merged, artifacts)

    assert result["missing_sources"] == ["source-b"]
    assert "no artifact received for 1 sources: source-b" in capsys.readouterr().out
