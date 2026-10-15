"""JSON persistence, shared by the pipeline and optional diagnostic renderer."""

import json
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path


def _encode(value: object) -> object:
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (set, frozenset)):
        return sorted(value)
    raise TypeError(f"cannot serialize {type(value).__name__}")


def write_json(path: Path, data: object) -> None:
    """Persist complete numerical outputs, never just a plot sample."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, default=_encode, indent=2, allow_nan=False) + "\n", encoding="utf-8")
