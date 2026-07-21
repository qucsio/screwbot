from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.categories import CATEGORIES
from bot.db.models import CreatorStatus, Lang, User
from bot.db.repositories.works import get_approved_creator, get_creator
from bot.handlers.beats import open_add_work, open_catalog
from bot.handlers.order_flow import open_orders
from bot.handlers.orders import start_order
from bot.handlers.portfolio import open_portfolio
from bot.handlers.profile import open_profile
from bot.handlers.reviews import open_reviews, start_review_upload
from bot.handlers.start import open_settings, start_creator_application
from bot.keyboards.common import creator_panel, main_menu, order_menu
from bot.locales import t

router = Router()


def _match(text: str, key: str) -> bool:
    """Сопоставление кнопки независимо от языка интерфейса."""
    return text in (t(key, Lang.ru), t(key, Lang.en))


async def _require_creator(message: Message, session: AsyncSession, user: User):
    """Гард исполнительских кнопок: возвращает Creator или None (+сообщение)."""
    creator = await get_approved_creator(session, user.id)
    if creator is None:
        await message.answer(t("profile_only_creator", user.lang))
    return creator


@router.message()
async def menu_router(
    message: Message, state: FSMContext, session: AsyncSession, user: User | None
):
    if user is None or user.role is None:
        return
    text = message.text or ""

    # --- Панель исполнителя (отдельная клавиатура) ---
    if _match(text, "menu_creator_panel"):
        creator = await get_approved_creator(session, user.id)
        if creator is None:
            await message.answer(t("profile_only_creator", user.lang))
            return
        await message.answer(t("menu_creator_panel", user.lang), reply_markup=creator_panel(user.lang))
        return
    if _match(text, "menu_back_main"):
        creator = await get_creator(session, user.id)
        status = creator.status if creator else None
        await message.answer(t("main_menu", user.lang), reply_markup=main_menu(user.lang, status))
        return
    if _match(text, "menu_my_profile"):
        if await _require_creator(message, session, user):
            await open_profile(message, session, user)
        return
    if _match(text, "menu_add_work"):
        if await _require_creator(message, session, user):
            await open_add_work(message, session, user)
        return
    if _match(text, "menu_portfolio"):
        if await _require_creator(message, session, user):
            await open_portfolio(message, state, session, user)
        return
    if _match(text, "menu_creator_orders"):
        if await _require_creator(message, session, user):
            await open_orders(message, state, session, user, as_creator=True)
        return
    if _match(text, "menu_upload_review"):
        if await _require_creator(message, session, user):
            await start_review_upload(message, state, session, user)
        return

    # --- Базовое меню (доступно всем) ---
    if _match(text, "menu_order_service"):
        await message.answer(t("menu_order_service", user.lang), reply_markup=order_menu(user.lang))
        return
    if _match(text, "menu_settings"):
        await open_settings(message, user)
        return
    if _match(text, "menu_become_creator"):
        await start_creator_application(message, state, session, user)
        return
    if _match(text, "menu_application_pending"):
        creator = await get_creator(session, user.id)
        if creator and creator.status == CreatorStatus.approved:
            await message.answer(t("creator_already_approved", user.lang))
        else:
            await message.answer(t("application_pending_info", user.lang))
        return

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
        await open_orders(message, state, session, user, as_creator=False)
    elif _match(text, "menu_reviews"):
        await open_reviews(message, state, session, user)
