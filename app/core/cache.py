import fnmatch
import json
import logging
import time
from typing import Any

import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger("app.cache")


class InMemoryFallbackCache:
    """Thread-safe in-memory cache used as a fallback when Redis is offline."""

    def __init__(self) -> None:
        self._store: dict[str, tuple[str, float]] = {}

    async def get(self, key: str) -> str | None:
        now = time.time()
        if key in self._store:
            val, expiry = self._store[key]
            if expiry > now:
                return val
            del self._store[key]
        return None

    async def set(self, key: str, value: str, ex: int = 120) -> None:
        self._store[key] = (value, time.time() + ex)

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)

    async def delete_pattern(self, pattern: str) -> None:
        keys_to_del = [k for k in self._store if fnmatch.fnmatch(k, pattern)]
        for k in keys_to_del:
            self._store.pop(k, None)

    async def flush(self) -> None:
        self._store.clear()


class CacheService:
    """Unified cache service supporting Redis with graceful in-memory fallback."""

    def __init__(self) -> None:
        self._redis: aioredis.Redis | None = None
        self._fallback = InMemoryFallbackCache()
        self._is_redis_available = False

    @property
    def is_redis_available(self) -> bool:
        """Returns True if connected to a live Redis server."""
        return self._is_redis_available

    async def init(self) -> None:
        """Attempt to connect to Redis on application startup."""
        if not settings.CACHE_ENABLED:
            logger.info("Cache is disabled by settings.")
            return

        try:
            self._redis = aioredis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_timeout=1.0,
                socket_connect_timeout=1.0,
            )
            await self._redis.ping()
            self._is_redis_available = True
            logger.info("Connected to Redis cache successfully.")
        except Exception as exc:
            self._is_redis_available = False
            logger.warning("Redis connection failed (%s). Using in-memory fallback cache.", exc)

    async def close(self) -> None:
        """Close Redis connection on shutdown."""
        if self._redis:
            try:
                await self._redis.aclose()
            except Exception:
                pass

    async def get(self, key: str) -> str | None:
        """Retrieve raw string value by key."""
        if not settings.CACHE_ENABLED:
            return None

        if self._is_redis_available and self._redis:
            try:
                res = await self._redis.get(key)
                if isinstance(res, bytes):
                    return res.decode("utf-8")
                return res
            except Exception as e:
                logger.warning("Redis get error (%s). Falling back to in-memory.", e)
        return await self._fallback.get(key)

    async def get_json(self, key: str) -> Any | None:
        """Retrieve and parse JSON serialized object from cache."""
        raw = await self.get(key)
        if raw is not None:
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return None
        return None

    async def set(self, key: str, value: str, ttl: int | None = None) -> None:
        """Store string value with TTL in seconds."""
        if not settings.CACHE_ENABLED:
            return

        effective_ttl = ttl if ttl is not None else settings.CACHE_TTL_SECONDS
        if self._is_redis_available and self._redis:
            try:
                await self._redis.set(key, value, ex=effective_ttl)
                return
            except Exception as e:
                logger.warning("Redis set error (%s). Falling back to in-memory.", e)
        await self._fallback.set(key, value, ex=effective_ttl)

    async def set_json(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Serialize object to JSON and store in cache with TTL."""
        effective_ttl = ttl if ttl is not None else settings.CACHE_TTL_SECONDS
        await self.set(key, json.dumps(value, default=str), ttl=effective_ttl)

    async def delete(self, key: str) -> None:
        """Delete specific key from cache."""
        if not settings.CACHE_ENABLED:
            return

        if self._is_redis_available and self._redis:
            try:
                await self._redis.delete(key)
                return
            except Exception:
                pass
        await self._fallback.delete(key)

    async def delete_pattern(self, pattern: str) -> None:
        """Invalidate keys matching wildcard pattern (e.g. 'tasks:project:1:*')."""
        if not settings.CACHE_ENABLED:
            return

        if self._is_redis_available and self._redis:
            try:
                keys = []
                async for key in self._redis.scan_iter(match=pattern):
                    keys.append(key)
                if keys:
                    await self._redis.delete(*keys)
                return
            except Exception as e:
                logger.warning("Redis delete_pattern error (%s). Falling back to in-memory.", e)
        await self._fallback.delete_pattern(pattern)

    async def clear_all(self) -> None:
        """Flush cache in both Redis and in-memory store."""
        if self._is_redis_available and self._redis:
            try:
                await self._redis.flushdb()
            except Exception:
                pass
        await self._fallback.flush()


cache_service = CacheService()
