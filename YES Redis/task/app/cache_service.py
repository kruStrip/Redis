"""
Сервис кэширования — Cache-Aside паттерн.

TTL-стратегия:
  - Авторы (справочник, меняются редко):  TTL 10 мин + jitter 0-60 с
  - Книга по ID (меняется при PATCH):      TTL 5 мин  + jitter 0-30 с
  - top-rated / popular (меняются редко): TTL 3 мин  + jitter 0-30 с
  - count (меняется при create/borrow):   TTL 1 мин  + jitter 0-15 с
  - search (много уникальных ключей):     TTL 2 мин  + jitter 0-20 с

НЕ кэшируем:
  - GET /books/          — взрыв ключей (offset × limit × author_id)
  - GET /borrowings/     — данные меняются при каждой выдаче/возврате
  - GET /borrowings/{id} — персональные, меняются при возврате
"""

from __future__ import annotations

import json
import logging
import random
from typing import Any

from app.redis_client import get_redis

logger = logging.getLogger("app.cache")

# ── Базовые TTL (секунды) ─────────────────────────────────
TTL_AUTHORS_LIST = 600
TTL_AUTHOR       = 600
TTL_BOOK         = 300
TTL_TOP_RATED    = 180
TTL_POPULAR      = 180
TTL_COUNT        = 60
TTL_SEARCH       = 120


def _ttl_with_jitter(base: int, jitter: int) -> int:
    return base + random.randint(0, jitter)


# ── Низкоуровневые операции ───────────────────────────────

async def cache_get(key: str) -> Any | None:
    try:
        redis = await get_redis()
        raw = await redis.get(key)
        if raw is None:
            return None
        return json.loads(raw)
    except Exception as exc:
        logger.warning("cache_get error key=%s: %s", key, exc)
        return None


async def cache_set(key: str, value: Any, ttl: int) -> None:
    try:
        redis = await get_redis()
        await redis.set(key, json.dumps(value, ensure_ascii=False), ex=ttl)
    except Exception as exc:
        logger.warning("cache_set error key=%s: %s", key, exc)


async def cache_delete(key: str) -> None:
    try:
        redis = await get_redis()
        await redis.delete(key)
    except Exception as exc:
        logger.warning("cache_delete error key=%s: %s", key, exc)


async def cache_delete_pattern(pattern: str) -> None:
    """Удалить ключи по шаблону через SCAN (не KEYS!)."""
    try:
        redis = await get_redis()
        cursor = 0
        while True:
            cursor, keys = await redis.scan(cursor, match=pattern, count=100)
            if keys:
                await redis.delete(*keys)
            if cursor == 0:
                break
    except Exception as exc:
        logger.warning("cache_delete_pattern error pattern=%s: %s", pattern, exc)


# ── Высокоуровневые функции ───────────────────────────────

# Authors
async def get_cached_authors_list() -> Any | None:
    return await cache_get("cache:authors:list")


async def set_cached_authors_list(data: Any) -> None:
    await cache_set("cache:authors:list", data, _ttl_with_jitter(TTL_AUTHORS_LIST, 60))


async def get_cached_author(author_id: int) -> Any | None:
    return await cache_get(f"cache:author:{author_id}")


async def set_cached_author(author_id: int, data: Any) -> None:
    await cache_set(f"cache:author:{author_id}", data, _ttl_with_jitter(TTL_AUTHOR, 60))


# Books
async def get_cached_book(book_id: int) -> Any | None:
    return await cache_get(f"cache:book:{book_id}")


async def set_cached_book(book_id: int, data: Any) -> None:
    await cache_set(f"cache:book:{book_id}", data, _ttl_with_jitter(TTL_BOOK, 30))


async def get_cached_top_rated(limit: int) -> Any | None:
    return await cache_get(f"cache:books:top_rated:{limit}")


async def set_cached_top_rated(limit: int, data: Any) -> None:
    await cache_set(f"cache:books:top_rated:{limit}", data, _ttl_with_jitter(TTL_TOP_RATED, 30))


async def get_cached_popular(limit: int) -> Any | None:
    return await cache_get(f"cache:books:popular:{limit}")


async def set_cached_popular(limit: int, data: Any) -> None:
    await cache_set(f"cache:books:popular:{limit}", data, _ttl_with_jitter(TTL_POPULAR, 30))


async def get_cached_count() -> Any | None:
    return await cache_get("cache:books:count")


async def set_cached_count(data: Any) -> None:
    await cache_set("cache:books:count", data, _ttl_with_jitter(TTL_COUNT, 15))


async def get_cached_search(q: str, limit: int) -> Any | None:
    return await cache_get(f"cache:books:search:{q.lower()}:{limit}")


async def set_cached_search(q: str, limit: int, data: Any) -> None:
    await cache_set(f"cache:books:search:{q.lower()}:{limit}", data, _ttl_with_jitter(TTL_SEARCH, 20))


# ── Инвалидация ───────────────────────────────────────────

async def invalidate_book(book_id: int) -> None:
    """Инвалидировать кэш конкретной книги + агрегаты."""
    await cache_delete(f"cache:book:{book_id}")
    await cache_delete_pattern("cache:books:top_rated:*")
    await cache_delete_pattern("cache:books:popular:*")
    await cache_delete("cache:books:count")
    await cache_delete_pattern("cache:books:search:*")


async def invalidate_book_availability(book_id: int) -> None:
    """При выдаче/возврате книги — инвалидировать её кэш и счётчик."""
    await cache_delete(f"cache:book:{book_id}")
    await cache_delete("cache:books:count")
    await cache_delete_pattern("cache:books:top_rated:*")
    await cache_delete_pattern("cache:books:popular:*")
