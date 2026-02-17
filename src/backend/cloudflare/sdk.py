from __future__ import annotations

import asyncio
import importlib
import sys
from pathlib import Path
from typing import Any


def _import_sdk():
    """
    Import the external `cloudflare` SDK without shadowing our local
    `dashboard.backend.cloudflare` package.
    """
    local_root = Path(__file__).resolve().parent.parent
    removed: list[str] = []
    # Remove any sys.path entries that resolve to local_root (including cwd alias "")
    for entry in list(sys.path):
        if entry in ("", "."):
            try:
                if Path.cwd().resolve() == local_root:
                    sys.path.remove(entry)
                    removed.append(entry)
            except Exception:
                continue
            continue
        try:
            if Path(entry).resolve() == local_root:
                sys.path.remove(entry)
                removed.append(entry)
        except Exception:
            continue
    # Drop shadowed module if it points to local package.
    mod = sys.modules.get("cloudflare")
    if mod and getattr(mod, "__file__", ""):
        try:
            if Path(mod.__file__).resolve().parent == (local_root / "cloudflare"):
                del sys.modules["cloudflare"]
        except Exception:
            pass
    try:
        return importlib.import_module("cloudflare")
    finally:
        for entry in reversed(removed):
            sys.path.insert(0, entry)


_sdk = _import_sdk()


class _Asyncify:
    def __init__(self, obj: Any):
        self._obj = obj

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self._obj, name)
        if callable(attr):
            async def _call(*args, **kwargs):
                return await asyncio.to_thread(attr, *args, **kwargs)
            return _call

        # Wrap nested SDK namespaces (e.g. dns.records.*)
        if hasattr(attr, "__dict__"):
            return _Asyncify(attr)
        return attr


if hasattr(_sdk, "AsyncCloudflare"):
    AsyncCloudflare = _sdk.AsyncCloudflare
else:
    # Fallback to sync client, wrapped with async proxy.
    SyncCloudflare = getattr(_sdk, "Cloudflare", None)
    if SyncCloudflare is None:
        raise ImportError("Cloudflare SDK missing AsyncCloudflare/Cloudflare classes")

    class AsyncCloudflare:  # type: ignore[override]
        def __init__(self, api_token: str):
            self._sync = SyncCloudflare(api_token=api_token)
            self._client = _Asyncify(self._sync._client)
            self.zones = _Asyncify(self._sync.zones)
            self.dns = _Asyncify(self._sync.dns)
