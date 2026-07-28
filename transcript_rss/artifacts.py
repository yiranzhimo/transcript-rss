from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Iterable

from .models import AppConfig
from .publish import rebuild_site
from .state import load_state, save_state

STATE_FRAGMENT_NAME = "state.fragment.json"


def _safe_slug(value: str) -> str:
    slug = str(value).strip()
    if not slug or Path(slug).name != slug or slug in {".", ".."}:
        raise ValueError(f"invalid item slug in artifact: {value!r}")
    return slug


def write_source_artifact(
    config: AppConfig,
    state: dict[str, Any],
    published_slugs: Iterable[str],
    artifact_dir: Path,
) -> None:
    source_ids = {source.id for source in config.sources}
    if not source_ids:
        raise ValueError("cannot write an artifact without selected sources")

    artifact_dir.mkdir(parents=True, exist_ok=True)
    fragment = {
        "version": 1,
        "sources": {
            source_id: state.get("sources", {}).get(source_id, {})
            for source_id in sorted(source_ids)
        },
        "items": {
            key: row
            for key, row in state.get("items", {}).items()
            if row.get("source_id") in source_ids
        },
    }
    (artifact_dir / STATE_FRAGMENT_NAME).write_text(
        json.dumps(fragment, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    artifact_items = artifact_dir / "items"
    output_items = config.site.output_dir / "items"
    for raw_slug in sorted(set(published_slugs)):
        slug = _safe_slug(raw_slug)
        source = output_items / slug
        if not source.is_dir():
            raise FileNotFoundError(f"generated item directory does not exist: {source}")
        shutil.copytree(source, artifact_items / slug, dirs_exist_ok=True)


def merge_source_artifacts(
    config: AppConfig,
    artifacts_dir: Path,
) -> dict[str, Any]:
    fragment_paths = sorted(artifacts_dir.glob(f"*/{STATE_FRAGMENT_NAME}"))
    if not fragment_paths:
        raise ValueError(f"no source artifacts found in {artifacts_dir}")

    configured_ids = {source.id for source in config.sources if source.enabled}
    state = load_state(config.site.state_file)
    state.setdefault("sources", {})
    state.setdefault("items", {})
    merged_sources: set[str] = set()
    copied_items = 0

    for fragment_path in fragment_paths:
        fragment = json.loads(fragment_path.read_text(encoding="utf-8"))
        if fragment.get("version") != 1:
            raise ValueError(f"unsupported artifact version in {fragment_path}")
        fragment_sources = fragment.get("sources")
        fragment_items = fragment.get("items")
        if not isinstance(fragment_sources, dict) or not isinstance(fragment_items, dict):
            raise ValueError(f"invalid state fragment in {fragment_path}")

        source_ids = set(fragment_sources)
        if not source_ids:
            raise ValueError(f"artifact contains no sources: {fragment_path}")
        unknown = source_ids - configured_ids
        duplicate = source_ids & merged_sources
        if unknown:
            raise ValueError(
                f"artifact contains unknown sources: {', '.join(sorted(unknown))}"
            )
        if duplicate:
            raise ValueError(
                f"duplicate source artifacts: {', '.join(sorted(duplicate))}"
            )

        for key, row in fragment_items.items():
            if not isinstance(row, dict) or row.get("source_id") not in source_ids:
                raise ValueError(f"item {key!r} does not belong to its artifact source")
            if row.get("item_slug"):
                _safe_slug(row["item_slug"])

        state["sources"].update(fragment_sources)
        state["items"].update(fragment_items)
        merged_sources.update(source_ids)

        item_root = fragment_path.parent / "items"
        if item_root.is_dir():
            for source in sorted(item_root.iterdir()):
                if not source.is_dir() or source.is_symlink():
                    continue
                slug = _safe_slug(source.name)
                shutil.copytree(
                    source,
                    config.site.output_dir / "items" / slug,
                    dirs_exist_ok=True,
                )
                copied_items += 1

    rebuild_site(config, config.sources, state)
    save_state(config.site.state_file, state)
    missing_sources = sorted(configured_ids - merged_sources)
    if missing_sources:
        print(
            f"[warn] no artifact received for {len(missing_sources)} sources: "
            f"{', '.join(missing_sources)}",
            flush=True,
        )
    return {
        "artifacts": len(fragment_paths),
        "sources": len(merged_sources),
        "items": copied_items,
        "missing_sources": missing_sources,
    }
