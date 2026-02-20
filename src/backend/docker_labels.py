from __future__ import annotations

import os
from typing import Mapping


def _compose_project_name() -> str:
    name = os.getenv("COMPOSE_PROJECT_NAME", "").strip()
    return name or "janus"


def compose_labels(service: str, *, kind: str = "", extra: Mapping[str, str] | None = None) -> dict[str, str]:
    labels: dict[str, str] = {
        "com.docker.compose.project": _compose_project_name(),
        "com.docker.compose.service": str(service or "runtime"),
        "com.docker.compose.oneoff": "False",
        "io.janus.managed": "true",
    }
    if kind:
        labels["io.janus.kind"] = str(kind)
    if extra:
        for key, value in extra.items():
            labels[str(key)] = str(value)
    return labels

