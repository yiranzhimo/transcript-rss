from __future__ import annotations

import argparse
import json
import sys

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
        stats = run_sync(config, fail_on_error=args.fail_on_error)
        print(json.dumps(stats, ensure_ascii=False))
        return 1 if args.fail_on_error and stats["failed"] else 0
    except (ConfigError, OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
