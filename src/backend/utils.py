import os
import json
from pathlib import Path
from typing import Dict


def ensure_parent(path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)


def read_json(path: str, default):
    if not os.path.exists(path):
        ensure_parent(path)
        return default
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: str, data: Dict):
    ensure_parent(path)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
