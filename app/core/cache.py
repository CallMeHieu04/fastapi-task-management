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

    async def sadd(self, set_name: str, value: str) -> None:
        key = f"set:{set_name}:{value}"
        self._store[key] = ("1", time.time() + 86400 * 7)

    async def sismember(self, set_name: str, value: str) -> bool:
        key = f"set:{set_name}:{value}"
        return await self.get(key) is not None


class CacheService:
    """Unified cache service supporting Redis with graceful in-memory fallback."""

    def __init__(self) -> None:
        self._redis: aioredis.Redis | None = None
        self._fallback = InMemoryFallbackCache()
        self._is_redis_available = False

    async def init(self) -> None:
        """Attempt to connect to Redis on application startup."""
        try:
            self._redis = aioredis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_timeout=2.0,
                socket_connect_timeout=2.0,
            )
            await self._redis.ping()
            self._is_redis_available = True
            logger.info("Connected to Redis cache successfully.")
        except Exception as exc:
            self._is_redis_available = False
            logger.warning(
                f"Redis connection failed ({exc}). Using in-memory fallback cache."
            )

    async def close(self) -> None:
        """Close Redis connection on shutdown."""
        if self._redis:
            try:
                await self._redis.aclose()
            except Exception:
                pass

    async def get(self, key: str) -> str | None:
        if self._is_redis_available and self._redis:
            try:
                res = await self._redis.get(key)
                if isinstance(res, bytes):
                    return res.decode("utf-8")
                return res
            except Exception as e:
                logger.warning(f"Redis get error: {e}. Falling back.")
        return await self._fallback.get(key)

    async def get_json(self, key: str) -> Any | None:
        raw = await self.get(key)
        if raw is not None:
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return None
        return None

    async def set(self, key: str, value: str, ttl: int = 120) -> None:
        if self._is_redis_available and self._redis:
            try:
                await self._redis.set(key, value, ex=ttl)
                return
            except Exception as e:
                logger.warning(f"Redis set error: {e}. Falling back.")
        await self._fallback.set(key, value, ex=ttl)

    async def set_json(self, key: str, value: Any, ttl: int = 120) -> None:
        await self.set(key, json.dumps(value, default=str), ttl=ttl)

    async def delete(self, key: str) -> None:
        if self._is_redis_available and self._redis:
            try:
                await self._redis.delete(key)
                return
            except Exception:
                pass
        await self._fallback.delete(key)

    async def delete_pattern(self, pattern: str) -> None:
        """Invalidate keys matching wildcard pattern (e.g. tasks:project:1:*)."""
        if self._is_redis_available and self._redis:
            try:
                keys = []
                async for key in self._redis.scan_iter(match=pattern):
                    keys.append(key)
                if keys:
                    await self._redis.delete(*keys)
                return
            except Exception as e:
                logger.warning(f"Redis delete_pattern error: {e}. Falling back.")
        await self._fallback.delete_pattern(pattern)

    async def revoke_token(self, token: str, expire_seconds: int = 86400 * 7) -> None:
        """Blacklist a revoked refresh token."""
        key = f"revoked_token:{token}"
        await self.set(key, "revoked", ttl=expire_seconds)

    async def is_token_revoked(self, token: str) -> bool:
        """Check if a refresh token has been revoked."""
        val = await self.get(f"revoked_token:{token}")
        return val == "revoked"


cache_service = CacheService()
