"""TTL-based caching for introspection results.

Uses stdlib only. Freqtrade codebase doesn't change during a session,
so a long TTL with manual invalidation support is appropriate.
"""

import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from functools import wraps
from typing import Any, ParamSpec, TypeVar

from freqtrade_mcp.constants import DEFAULT_CACHE_MAXSIZE, DEFAULT_CACHE_TTL

P = ParamSpec("P")
R = TypeVar("R")


class TTLCache:
    """Thread-safe, bounded TTL cache for storing introspection results.

    Entries expire after ``ttl`` seconds and the least recently used entry is
    evicted once ``maxsize`` is exceeded. The bound matters because expired
    entries are only dropped when their key is read again: without it, every
    distinct query would hold its full result list for the whole TTL.

    Args:
        ttl: Time-to-live in seconds for cached entries.
        maxsize: Maximum number of entries to retain.
    """

    def __init__(
        self,
        ttl: int = DEFAULT_CACHE_TTL,
        maxsize: int = DEFAULT_CACHE_MAXSIZE,
    ) -> None:
        """Initialize the cache.

        Args:
            ttl: Time-to-live in seconds for cached entries.
            maxsize: Maximum number of entries to retain (must be >= 1).
        """
        self._ttl = ttl
        self._maxsize = max(1, maxsize)
        self._cache: OrderedDict[str, tuple[float, Any]] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str) -> Any | None:
        """Get a value from cache if it exists and hasn't expired.

        Args:
            key: Cache key.

        Returns:
            Cached value or None if not found/expired.
        """
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            timestamp, value = entry
            if time.monotonic() - timestamp > self._ttl:
                del self._cache[key]
                return None
            self._cache.move_to_end(key)
            return value

    def set(self, key: str, value: Any) -> None:
        """Store a value in the cache, evicting the oldest entry if needed.

        Args:
            key: Cache key.
            value: Value to cache.
        """
        with self._lock:
            self._cache[key] = (time.monotonic(), value)
            self._cache.move_to_end(key)
            while len(self._cache) > self._maxsize:
                self._cache.popitem(last=False)

    def invalidate(self, key: str) -> None:
        """Remove a specific entry from the cache.

        Args:
            key: Cache key to remove.
        """
        with self._lock:
            self._cache.pop(key, None)

    def clear(self) -> None:
        """Remove all entries from the cache."""
        with self._lock:
            self._cache.clear()

    @property
    def size(self) -> int:
        """Return the number of entries in the cache (including expired)."""
        with self._lock:
            return len(self._cache)


# Global cache instance
_global_cache = TTLCache()


def get_cache() -> TTLCache:
    """Get the global cache instance.

    Returns:
        The global TTLCache instance.
    """
    return _global_cache


def ttl_cache(
    ttl: int = DEFAULT_CACHE_TTL,
    maxsize: int = DEFAULT_CACHE_MAXSIZE,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator that caches function results with a TTL and a size bound.

    Args:
        ttl: Time-to-live in seconds.
        maxsize: Maximum number of cached results to retain.

    Returns:
        Decorator function.
    """
    cache = TTLCache(ttl=ttl, maxsize=maxsize)

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            # Build cache key from function name and arguments
            key_parts = [func.__qualname__]
            key_parts.extend(repr(a) for a in args)
            key_parts.extend(f"{k}={v!r}" for k, v in sorted(kwargs.items()))
            key = ":".join(key_parts)

            # Results are wrapped in a 1-tuple so that None results are cacheable too
            hit = cache.get(key)
            if hit is not None:
                return hit[0]  # type: ignore[no-any-return]

            result = func(*args, **kwargs)
            cache.set(key, (result,))
            return result

        # Expose cache for manual invalidation
        wrapper.cache = cache  # type: ignore[attr-defined]
        return wrapper

    return decorator
