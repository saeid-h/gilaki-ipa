from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from .settings import settings


def _presets_path() -> Path:
    return Path(settings.presets_dir).resolve()


@lru_cache(maxsize=1)
def load_inventory() -> dict:
    return json.loads(Path(settings.inventory_path).resolve().read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_presets() -> dict[str, dict]:
    presets = {}
    root = _presets_path()
    for file in sorted(root.glob("*.json")):
        data = json.loads(file.read_text(encoding="utf-8"))
        presets[data["id"]] = data
    return presets


def list_preset_summaries() -> list[dict]:
    rows = []
    for item in load_presets().values():
        rows.append(
            {
                "id": item["id"],
                "name": item["name"],
                "script": item["script"],
                "direction": item.get("direction", "ltr"),
                "lossy": item.get("lossy", False),
                "description": item.get("description", ""),
            }
        )
    return rows


def get_preset(preset_id: str) -> dict | None:
    return load_presets().get(preset_id)
