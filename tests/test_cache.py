"""Tests for TTL cache behavior."""

import time

from freqtrade_mcp.cache import TTLCache, ttl_cache


class TestTTLCache:
    """Tests for the TTLCache class."""

    def test_set_and_get(self) -> None:
        """Values can be stored and retrieved."""
        cache = TTLCache(ttl=60)
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_missing_key_returns_none(self) -> None:
        """Missing keys return None."""
        cache = TTLCache(ttl=60)
        assert cache.get("nonexistent") is None

    def test_expired_entry_returns_none(self) -> None:
        """Expired entries return None and are cleaned up."""
        cache = TTLCache(ttl=0)  # Immediate expiry
        cache.set("key1", "value1")
        time.sleep(0.01)
        assert cache.get("key1") is None

    def test_invalidate(self) -> None:
        """Invalidate removes a specific entry."""
        cache = TTLCache(ttl=60)
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.invalidate("key1")
        assert cache.get("key1") is None
        assert cache.get("key2") == "value2"

    def test_invalidate_nonexistent(self) -> None:
        """Invalidating a nonexistent key should not raise."""
        cache = TTLCache(ttl=60)
        cache.invalidate("nonexistent")  # Should not raise

    def test_clear(self) -> None:
        """Clear removes all entries."""
        cache = TTLCache(ttl=60)
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.clear()
        assert cache.get("key1") is None
        assert cache.get("key2") is None
        assert cache.size == 0

    def test_size(self) -> None:
        """Size returns number of entries."""
        cache = TTLCache(ttl=60)
        assert cache.size == 0
        cache.set("key1", "value1")
        assert cache.size == 1
        cache.set("key2", "value2")
        assert cache.size == 2

    def test_overwrite(self) -> None:
        """Setting same key overwrites previous value."""
        cache = TTLCache(ttl=60)
        cache.set("key1", "old")
        cache.set("key1", "new")
        assert cache.get("key1") == "new"
        assert cache.size == 1


class TestTTLCacheBounds:
    """Tests for the size bound and LRU eviction."""

    def test_evicts_when_over_maxsize(self) -> None:
        """The cache must not grow past maxsize.

        Expired entries are only dropped when their key is read again, so
        without a bound every distinct query holds its result for the full TTL.
        """
        cache = TTLCache(ttl=60, maxsize=3)
        for i in range(10):
            cache.set(f"key{i}", i)
        assert cache.size == 3

    def test_evicts_least_recently_used(self) -> None:
        """Reading an entry protects it from the next eviction."""
        cache = TTLCache(ttl=60, maxsize=2)
        cache.set("a", 1)
        cache.set("b", 2)

        assert cache.get("a") == 1  # "a" becomes the most recently used
        cache.set("c", 3)  # evicts "b"

        assert cache.get("a") == 1
        assert cache.get("b") is None
        assert cache.get("c") == 3

    def test_maxsize_is_at_least_one(self) -> None:
        """A degenerate maxsize must not disable caching entirely."""
        cache = TTLCache(ttl=60, maxsize=0)
        cache.set("a", 1)
        assert cache.get("a") == 1
        assert cache.size == 1

    def test_none_value(self) -> None:
        """None can be stored but get returns None for missing keys too.

        This is a known limitation: cannot distinguish stored None from missing.
        """
        cache = TTLCache(ttl=60)
        cache.set("key1", None)
        # Returns None — ambiguous with "not found"
        assert cache.get("key1") is None


class TestTTLCacheDecorator:
    """Tests for the ttl_cache decorator."""

    def test_caches_result(self) -> None:
        """Decorated function result should be cached."""
        call_count = 0

        @ttl_cache(ttl=60)
        def expensive_function(x: int) -> int:
            nonlocal call_count
            call_count += 1
            return x * 2

        assert expensive_function(5) == 10
        assert expensive_function(5) == 10
        assert call_count == 1  # Only called once

    def test_different_args_different_cache(self) -> None:
        """Different arguments should produce different cache entries."""
        call_count = 0

        @ttl_cache(ttl=60)
        def add(a: int, b: int) -> int:
            nonlocal call_count
            call_count += 1
            return a + b

        assert add(1, 2) == 3
        assert add(3, 4) == 7
        assert call_count == 2

    def test_cache_expiry(self) -> None:
        """Cache should expire after TTL."""
        call_count = 0

        @ttl_cache(ttl=0)  # Immediate expiry
        def get_time() -> int:
            nonlocal call_count
            call_count += 1
            return call_count

        result1 = get_time()
        time.sleep(0.01)
        result2 = get_time()
        assert result2 > result1

    def test_cache_attribute_exposed(self) -> None:
        """Decorated function should expose cache for manual invalidation."""

        @ttl_cache(ttl=60)
        def my_func() -> str:
            return "result"

        assert hasattr(my_func, "cache")
        assert isinstance(my_func.cache, TTLCache)  # type: ignore[union-attr]

    def test_kwargs_cached(self) -> None:
        """Keyword arguments should be part of cache key."""
        call_count = 0

        @ttl_cache(ttl=60)
        def greet(name: str = "world") -> str:
            nonlocal call_count
            call_count += 1
            return f"hello {name}"

        assert greet(name="alice") == "hello alice"
        assert greet(name="alice") == "hello alice"
        assert greet(name="bob") == "hello bob"
        assert call_count == 2

    def test_none_result_cached(self) -> None:
        """A None return value should be cached, not recomputed."""
        call_count = 0

        @ttl_cache(ttl=60)
        def lookup() -> None:
            nonlocal call_count
            call_count += 1

        assert lookup() is None
        assert lookup() is None
        assert call_count == 1
