"""Идемпотентный сид справочника категорий.

Запуск: python -m bot.seed
thread_id проставляются позже (в БД или через админку) — здесь 0.
is_custom=True — услуга «на заказ» (нужен топик-тендер).
"""
import asyncio

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert

from bot.config import get_settings
from bot.db.models import Category
from bot.db.session import session_factory

CATEGORIES = [
    # code,           title_ru,                    title_en,                  is_custom
    ("ready_beats",   "Готовые биты",              "Ready beats",             False),
    ("custom_beats",  "Биты на заказ",             "Custom beats",            True),
    ("mixing",        "Mixing / Сведение",         "Mixing",                  True),
    ("ghostwriting",  "Текст (ghostwriting)",      "Ghostwriting",            True),
    ("visual",        "Визуал",                    "Visuals",                 True),
    ("videographer",  "Видеограф",                 "Videographer",            True),
    ("editing",       "Монтаж",                    "Video editing",           True),
    ("photo",         "Фото-сессия (Москва)",      "Photoshoot (Moscow)",     True),
]


async def seed() -> None:
    async with session_factory() as session:
        for code, ru, en, is_custom in CATEGORIES:
            stmt = (
                insert(Category)
                .values(code=code, title_ru=ru, title_en=en, is_custom=is_custom)
                .on_conflict_do_nothing(index_elements=["code"])
            )
            await session.execute(stmt)

        # проставляем/обновляем thread_id категорий из конфига
        for code, thread_id in get_settings().category_threads.items():
            if thread_id:
                await session.execute(
                    update(Category).where(Category.code == code).values(thread_id=thread_id)
                )
        await session.commit()

        result = await session.execute(select(Category.code))
        print("Categories:", ", ".join(sorted(result.scalars().all())))


if __name__ == "__main__":
    asyncio.run(seed())
