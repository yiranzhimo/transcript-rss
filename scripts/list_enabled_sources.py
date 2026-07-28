from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml


def main() -> int:
    config_path = Path(sys.argv[1] if len(sys.argv) > 1 else "config.yaml")
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    rows = raw.get("sources") or []
    source_ids = [
        str(row.get("id", "")).strip()
        for row in rows
        if isinstance(row, dict) and row.get("enabled", True)
    ]
    if not source_ids or any(not source_id for source_id in source_ids):
        raise ValueError("config must contain at least one enabled source with an id")
    if len(source_ids) != len(set(source_ids)):
        raise ValueError("enabled source ids must be unique")
    print(f"sources={json.dumps(source_ids, ensure_ascii=True, separators=(',', ':'))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
