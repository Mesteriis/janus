from __future__ import annotations

import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator

_correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)


def get_correlation_id() -> str | None:
    return _correlation_id.get()


def set_correlation_id(value: str) -> object:
    return _correlation_id.set(value)


def reset_correlation_id(token: object) -> None:
    _correlation_id.reset(token)


def ensure_correlation_id() -> str:
    value = _correlation_id.get()
    if value:
        return value
    value = str(uuid.uuid4())
    _correlation_id.set(value)
    return value


@contextmanager
def correlation_context(value: str) -> Iterator[str]:
    token = _correlation_id.set(value)
    try:
        yield value
    finally:
        _correlation_id.reset(token)
