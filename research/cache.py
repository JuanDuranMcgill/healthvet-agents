"""Simple JSON-backed query cache, keyed by normalized query + provider.

Short TTL, trivially disabled via the ``enabled`` flag or the
``RESEARCH_CACHE_DISABLED`` env var. Stores JSON-serializable payloads only.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Callable

_DISABLE_VALUES = {"1", "true", "yes", "on"}


def _key(query: str, provider: str) -> str:
    norm = f"{provider}::{(query or '').strip().lower()}"
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


class QueryCache:
    def __init__(
        self,
        path: str = ".research_cache.json",
        ttl_seconds: int = 3600,
        enabled: bool | None = None,
        now: Callable[[], float] = time.time,
    ):
        self.path = Path(path)
        self.ttl = ttl_seconds
        self._now = now
        if enabled is None:
            enabled = os.getenv("RESEARCH_CACHE_DISABLED", "").lower() not in _DISABLE_VALUES
        self.enabled = enabled
        self._data: dict[str, dict] = self._load()

    def _load(self) -> dict[str, dict]:
        if not self.path.exists():
            return {}
        try:
            return json.loads(self.path.read_text())
        except (json.JSONDecodeError, OSError):
            return {}

    def _flush(self) -> None:
        try:
            self.path.write_text(json.dumps(self._data))
        except OSError:
            pass

    def get(self, query: str, provider: str) -> Any | None:
        if not self.enabled:
            return None
        entry = self._data.get(_key(query, provider))
        if not entry:
            return None
        if self._now() - entry["ts"] > self.ttl:
            return None
        return entry["value"]

    def set(self, query: str, provider: str, value: Any) -> None:
        if not self.enabled:
            return
        self._data[_key(query, provider)] = {"ts": self._now(), "value": value}
        self._flush()
