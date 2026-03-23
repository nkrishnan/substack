"""Simple file-based JSON cache for Substack API responses."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Optional


class Cache:
    """Store raw API responses on disk as JSON files.

    Keys are arbitrary strings (e.g. ``"posts:https://pub.substack.com"``).
    Each key is hashed to a safe filename so no escaping is needed.

    Usage::

        cache = Cache("~/.cache/substack")
        raw = cache.get(key)
        if raw is None:
            raw = client.get(...)
            cache.set(key, raw)
    """

    def __init__(self, cache_dir: str | Path) -> None:
        self._dir = Path(cache_dir).expanduser()
        self._dir.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        digest = hashlib.sha256(key.encode()).hexdigest()
        return self._dir / f"{digest}.json"

    def get(self, key: str) -> Optional[Any]:
        """Return the cached value for *key*, or ``None`` if not present."""
        p = self._path(key)
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
        return None

    def set(self, key: str, data: Any) -> None:
        """Persist *data* (must be JSON-serialisable) under *key*."""
        self._path(key).write_text(
            json.dumps(data, ensure_ascii=False), encoding="utf-8"
        )

    def invalidate(self, key: str) -> None:
        """Remove the cached entry for *key* (no-op if absent)."""
        p = self._path(key)
        if p.exists():
            p.unlink()

    def clear(self) -> None:
        """Delete every cached entry in this cache directory."""
        for p in self._dir.glob("*.json"):
            p.unlink()
