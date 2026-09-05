from abc import ABC, abstractmethod
from typing import Optional
import json
import redis.asyncio as redis
from app.config import get_settings


settings = get_settings()


class CacheInterface(ABC):
    @abstractmethod
    async def get(self, key: str) -> Optional[str]:
        pass

    @abstractmethod
    async def set(self, key: str, value: str, expire: Optional[int] = None) -> None:
        pass

    @abstractmethod
    async def delete(self, key: str) -> None:
        pass

    @abstractmethod
    async def exists(self, key: str) -> bool:
        pass

    @abstractmethod
    async def close(self) -> None:
        pass


class MemoryCache(CacheInterface):
    def __init__(self):
        self._cache: dict[str, tuple[str, Optional[int]]] = {}

    async def get(self, key: str) -> Optional[str]:
        if key in self._cache:
            value, expire = self._cache[key]
            return value
        return None

    async def set(self, key: str, value: str, expire: Optional[int] = None) -> None:
        self._cache[key] = (value, expire)

    async def delete(self, key: str) -> None:
        if key in self._cache:
            del self._cache[key]

    async def exists(self, key: str) -> bool:
        return key in self._cache

    async def close(self) -> None:
        self._cache.clear()


class RedisCache(CacheInterface):
    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self._client: Optional[redis.Redis] = None

    async def _get_client(self) -> redis.Redis:
        if self._client is None:
            self._client = redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
        return self._client

    async def get(self, key: str) -> Optional[str]:
        client = await self._get_client()
        return await client.get(key)

    async def set(self, key: str, value: str, expire: Optional[int] = None) -> None:
        client = await self._get_client()
        if expire:
            await client.setex(key, expire, value)
        else:
            await client.set(key, value)

    async def delete(self, key: str) -> None:
        client = await self._get_client()
        await client.delete(key)

    async def exists(self, key: str) -> bool:
        client = await self._get_client()
        return await client.exists(key) > 0

    async def close(self) -> None:
        if self._client:
            await self._client.close()
            self._client = None


_cache_instance: Optional[CacheInterface] = None


def get_cache() -> CacheInterface:
    global _cache_instance
    if _cache_instance is None:
        if settings.REDIS_ENABLED:
            _cache_instance = RedisCache(settings.REDIS_URL)
        else:
            _cache_instance = MemoryCache()
    return _cache_instance


async def close_cache() -> None:
    global _cache_instance
    if _cache_instance is not None:
        await _cache_instance.close()
        _cache_instance = None
