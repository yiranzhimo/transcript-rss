from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .artifacts import merge_source_artifacts
from .config import ConfigError, load_config
from .pipeline import run_sync


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="transcript-feed",
        description="Generate Chinese transcript RSS feeds from podcasts and YouTube.",
    )
    parser.add_argument("--config", default="config.yaml", help="path to YAML configuration")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("validate", help="validate configuration and exit")
    sync = subparsers.add_parser("sync", help="discover, transcribe, translate, and publish")
    sync.add_argument(
        "--fail-on-error",
        action="store_true",
        help="stop at the first source or item error",
    )
    sync.add_argument(
        "--source",
        action="append",
        default=[],
        help="only process this source id; may be supplied more than once",
    )
    sync.add_argument(
        "--artifact-dir",
        help="write a mergeable source artifact and defer global RSS rebuilding",
    )
    merge = subparsers.add_parser(
        "merge-artifacts",
        help="merge source artifacts, rebuild feeds, and update state",
    )
    merge.add_argument("--artifacts-dir", required=True, help="downloaded artifacts directory")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        config = load_config(args.config)
        if args.command == "validate":
            print(
                json.dumps(
                    {
                        "status": "ok",
                        "sources": len(config.sources),
                        "output_dir": str(config.site.output_dir),
                        "base_url": config.site.base_url,
                    },
                    ensure_ascii=False,
                )
            )
            return 0
        if args.command == "merge-artifacts":
            stats = merge_source_artifacts(config, Path(args.artifacts_dir).resolve())
            print(json.dumps(stats, ensure_ascii=False))
            return 0

        if args.source:
            selected_ids = set(args.source)
            configured_ids = {source.id for source in config.sources}
            unknown = selected_ids - configured_ids
            if unknown:
                raise ConfigError(f"unknown source id: {', '.join(sorted(unknown))}")
            config.sources = [
                source for source in config.sources if source.id in selected_ids
            ]
        artifact_dir = Path(args.artifact_dir).resolve() if args.artifact_dir else None
        stats = run_sync(
            config,
            fail_on_error=args.fail_on_error,
            artifact_dir=artifact_dir,
        )
        print(json.dumps(stats, ensure_ascii=False))
        return 1 if args.fail_on_error and stats["failed"] else 0
    except (ConfigError, OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
