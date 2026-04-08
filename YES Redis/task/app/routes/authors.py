"""
Роуты авторов — с Redis-кэшем (Cache-Aside).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache_service import (
    get_cached_author,
    get_cached_authors_list,
    set_cached_author,
    set_cached_authors_list,
)
from app.db import get_session
from app.models import Author

router = APIRouter(prefix="/authors", tags=["authors"])


@router.get("/")
async def list_authors(session: AsyncSession = Depends(get_session)):
    """Список всех авторов."""
    cached = await get_cached_authors_list()
    if cached is not None:
        return cached

    result = await session.execute(select(Author).order_by(Author.id))
    authors = result.scalars().all()
    data = [a.to_dict() for a in authors]

    await set_cached_authors_list(data)
    return data


@router.get("/{author_id}")
async def get_author(
    author_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Страница автора по ID."""
    cached = await get_cached_author(author_id)
    if cached is not None:
        return cached

    result = await session.execute(select(Author).where(Author.id == author_id))
    author = result.scalar_one_or_none()
    if not author:
        raise HTTPException(404, "Author not found")

    data = author.to_dict()
    await set_cached_author(author_id, data)
    return data
