"""Идемпотентный сид категорий из единого реестра bot/categories.py.

Запуск: python -m bot.seed
thread_id берутся из окружения (<CODE>_THREAD_ID) через CategoryDef.thread_id.
"""
import asyncio

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert

from bot.categories import CATEGORIES
from bot.db.models import Category
from bot.db.session import session_factory


async def seed() -> None:
    async with session_factory() as session:
        for c in CATEGORIES:
            stmt = (
                insert(Category)
                .values(
                    code=c.code,
                    title_ru=c.ru,
                    title_en=c.en,
                    is_custom=(c.kind == "custom"),
                )
                .on_conflict_do_update(
                    index_elements=["code"],
                    set_={"title_ru": c.ru, "title_en": c.en, "is_custom": (c.kind == "custom")},
                )
            )
            await session.execute(stmt)
            if c.thread_id:
                await session.execute(
                    update(Category).where(Category.code == c.code).values(thread_id=c.thread_id)
                )
        await session.commit()

        result = await session.execute(select(Category.code))
        print("Categories:", ", ".join(sorted(result.scalars().all())))


if __name__ == "__main__":
    asyncio.run(seed())
