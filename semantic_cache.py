from __future__ import annotations

import hashlib
import json
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Protocol

from settings import Settings


class SemanticCache(Protocol):
    def get(self, key: str) -> Any | None:
        ...

    def set(self, key: str, value: Any) -> None:
        ...


class NullSemanticCache:
    def get(self, key: str) -> Any | None:
        return None

    def set(self, key: str, value: Any) -> None:
        return None


class MemorySemanticCache:
    def __init__(self, max_entries: int = 512) -> None:
        self._max_entries = max(1, int(max_entries))
        self._entries: OrderedDict[str, Any] = OrderedDict()

    def get(self, key: str) -> Any | None:
        if key not in self._entries:
            return None
        self._entries.move_to_end(key)
        return self._entries[key]

    def set(self, key: str, value: Any) -> None:
        self._entries[key] = value
        self._entries.move_to_end(key)
        while len(self._entries) > self._max_entries:
            self._entries.popitem(last=False)


def build_cache_key(operation: str, payload: dict[str, Any]) -> str:
    serialized = json.dumps(
        {
            "operation": operation,
            "payload": payload,
        },
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def build_semantic_cache(settings: Settings) -> SemanticCache:
    if settings.semantris_cache_backend == "memory":
        return MemorySemanticCache(max_entries=settings.semantris_cache_max_entries)
    return NullSemanticCache()
