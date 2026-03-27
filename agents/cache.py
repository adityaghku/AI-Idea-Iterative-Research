"""Response cache with TTL for LLM calls to avoid redundant evaluations."""
from __future__ import annotations

import hashlib
import logging
import time
from threading import Lock
from typing import Any

from .logger import get_logger

DEFAULT_TTL_SECONDS = 3600


class ResponseCache:
    """In-memory cache with TTL for LLM responses."""

    _instance: ResponseCache | None = None
    _lock = Lock()

    def __init__(self, ttl_seconds: int = DEFAULT_TTL_SECONDS):
        self._cache: dict[str, tuple[float, Any]] = {}
        self._ttl = ttl_seconds
        self._hits = 0
        self._misses = 0
        self.logger = get_logger()

    @classmethod
    def get_instance(cls, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> ResponseCache:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(ttl_seconds)
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        with cls._lock:
            if cls._instance is not None:
                cls._instance._cache.clear()
                cls._instance._hits = 0
                cls._instance._misses = 0
            cls._instance = None

    @staticmethod
    def content_hash(text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()

    def get(self, key: str) -> tuple[bool, Any]:
        if key in self._cache:
            timestamp, response = self._cache[key]
            age = time.time() - timestamp
            
            if age < self._ttl:
                self._hits += 1
                self.logger.debug(
                    f"Cache HIT (age={age:.0f}s, ttl={self._ttl}s, "
                    f"hits={self._hits}, misses={self._misses})"
                )
                return True, response
            else:
                del self._cache[key]
                self.logger.debug(f"Cache EXPIRED (age={age:.0f}s > ttl={self._ttl}s)")

        self._misses += 1
        self.logger.debug(
            f"Cache MISS (hits={self._hits}, misses={self._misses})"
        )
        return False, None

    def set(self, key: str, response: Any) -> None:
        if response is None:
            self.logger.warning("Skipping cache set for None response")
            return
        
        self._cache[key] = (time.time(), response)
        self.logger.debug(f"Cache SET (key={key[:16]}..., ttl={self._ttl}s)")

    def stats(self) -> dict[str, Any]:
        total = self._hits + self._misses
        hit_rate = self._hits / total if total > 0 else 0.0
        return {
            "hits": self._hits,
            "misses": self._misses,
            "total_requests": total,
            "hit_rate": hit_rate,
            "entries": len(self._cache),
            "ttl_seconds": self._ttl,
        }
