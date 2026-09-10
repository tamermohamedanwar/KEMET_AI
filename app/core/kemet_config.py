from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "config" / "kemet" / "global_defaults.json"


def load_global_defaults() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def get_setting(*keys: str, default: Any = None) -> Any:
    value: Any = load_global_defaults()

    for key in keys:
        if not isinstance(value, dict) or key not in value:
            return default
        value = value[key]

    return value
