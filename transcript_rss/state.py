from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def empty_state() -> dict[str, Any]:
    return {"version": 1, "sources": {}, "items": {}}


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return empty_state()
    state = json.loads(path.read_text(encoding="utf-8"))
    if state.get("version") != 1:
        raise ValueError(f"unsupported state version in {path}")
    state.setdefault("sources", {})
    state.setdefault("items", {})
    return state


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(
        json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temp_path.replace(path)
