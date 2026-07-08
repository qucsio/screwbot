from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.categories import CATEGORIES
from bot.db.models import Lang, Role, User
from bot.handlers.beats import open_add_work, open_catalog
from bot.handlers.order_flow import open_orders
from bot.handlers.orders import start_order
from bot.handlers.profile import open_profile
from bot.handlers.reviews import open_reviews
from bot.locales import t

router = Router()


def _match(text: str, key: str) -> bool:
    """Сопоставление кнопки независимо от языка интерфейса."""
    return text in (t(key, Lang.ru), t(key, Lang.en))


@router.message()
async def menu_router(
    message: Message, state: FSMContext, session: AsyncSession, user: User | None
):
    if user is None or user.role is None:
        return
    text = message.text or ""

    # --- Меню исполнителя ---
    if user.role == Role.creator:
        if _match(text, "menu_my_profile"):
            await open_profile(message, session, user)
        elif _match(text, "menu_add_work"):
            await open_add_work(message, session, user)
        elif _match(text, "menu_my_orders"):
            await open_orders(message, state, session, user)
        elif _match(text, "menu_reviews"):
            await open_reviews(message, state, session, user)
        return

    # --- Меню клиента ---
    for cat in CATEGORIES:
        if text in (cat.ru, cat.en):
            if cat.kind == "catalog":
                await open_catalog(message, state, session, user, cat.code)
            elif cat.kind == "custom":
                await start_order(message, state, session, user, cat.code)
            else:
                await message.answer(f"{text}\n\n{t('wip', user.lang)}")
            return

    if _match(text, "menu_my_orders"):
        await open_orders(message, state, session, user)
    elif _match(text, "menu_reviews"):
        await open_reviews(message, state, session, user)
