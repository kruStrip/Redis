"""
Redis singleton-клиент.
"""

from __future__ import annotations

import logging

import redis.asyncio as aioredis

from app.config import settings

logger = logging.getLogger("app.redis")

_redis: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    """Вернуть singleton-подключение к Redis."""
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis


async def close_redis() -> None:
    """Закрыть пул соединений при остановке приложения."""
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None
        logger.info("Redis connection closed")
