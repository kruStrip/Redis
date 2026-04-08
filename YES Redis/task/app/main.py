"""
FastAPI приложение — онлайн-библиотека.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.redis_client import close_redis, get_redis
from app.routes import authors, books, borrowings
from app.seed import seed_database

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(name)-12s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🗄️  Инициализация БД…")
    count = await seed_database()
    logger.info("✅ БД готова — %d книг", count)

    logger.info("🔴 Подключение к Redis…")
    redis = await get_redis()
    await redis.ping()
    logger.info("✅ Redis готов")

    yield

    await close_redis()
    logger.info("🔴 Redis отключён")


app = FastAPI(
    title="Library API — с Redis-кэшем",
    description="Онлайн-библиотека. Cache-Aside через Redis.",
    version="2.0.0",
    lifespan=lifespan,
)

app.include_router(authors.router)
app.include_router(books.router)
app.include_router(borrowings.router)


@app.get("/health")
async def health():
    return {"status": "ok", "cache": "redis"}
