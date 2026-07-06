from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import User
from bot.forms import MENU_TO_CODE
from bot.handlers.beats import open_catalog
from bot.handlers.orders import start_order
from bot.locales import t

router = Router()

# Ключи локализации всех пунктов меню — для сопоставления нажатой кнопки.
_MENU_KEYS = [
    "menu_ready_beats",
    "menu_custom_beats",
    "menu_mixing",
    "menu_ghostwriting",
    "menu_visual",
    "menu_videographer",
    "menu_editing",
    "menu_photo",
    "menu_reviews",
]


@router.message()
async def menu_router(
    message: Message, state: FSMContext, session: AsyncSession, user: User | None
):
    """Распознаёт нажатый пункт меню и роутит в модуль (или заглушку)."""
    if user is None or user.role is None:
        return
    text = message.text or ""

    # Готовые биты — рабочий каталог
    if text == t("menu_ready_beats", user.lang):
        await open_catalog(message, state, session, user)
        return

    # Услуги на заказ — запуск формы ТЗ
    for menu_key, code in MENU_TO_CODE.items():
        if text == t(menu_key, user.lang):
            await start_order(message, state, session, user, code)
            return

    for key in _MENU_KEYS:
        if text == t(key, user.lang):
            await message.answer(f"{text}\n\n{t('wip', user.lang)}")
            return
