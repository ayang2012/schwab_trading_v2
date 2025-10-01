"""Small utilities for IO operations in v2 sandbox."""
import json
from pathlib import Path
from typing import Any


def safe_write_json(path: Path, obj: Any, indent: int = 2) -> None:
    """Atomically write JSON to path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=indent, default=str)
        f.flush()
    tmp.replace(path)
