from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.categories import CATEGORIES
from bot.db.models import User
from bot.handlers.beats import open_catalog
from bot.handlers.order_flow import open_orders
from bot.handlers.orders import start_order
from bot.handlers.reviews import open_reviews
from bot.locales import t

router = Router()


@router.message()
async def menu_router(
    message: Message, state: FSMContext, session: AsyncSession, user: User | None
):
    """Матчит нажатую кнопку меню по реестру категорий и роутит по kind."""
    if user is None or user.role is None:
        return
    text = message.text or ""

    for cat in CATEGORIES:
        if text in (cat.ru, cat.en):
            if cat.kind == "catalog":
                await open_catalog(message, state, session, user, cat.code)
            elif cat.kind == "custom":
                await start_order(message, state, session, user, cat.code)
            else:
                await message.answer(f"{text}\n\n{t('wip', user.lang)}")
            return

    # «Мои заказы»
    if text == t("menu_my_orders", user.lang):
        await open_orders(message, state, session, user)
        return

    # «Отзывы»
    if text == t("menu_reviews", user.lang):
        await open_reviews(message, state, session, user)
