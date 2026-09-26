from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.categories import CATEGORIES
from bot.db.models import CreatorStatus, Lang, User
from bot.db.repositories import profiles as profiles_repo
from bot.db.repositories.works import get_approved_creator
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
# Подключается раньше всех форм (см. handlers/__init__.py).
nav_router = Router()

# Подписи всех кнопок нижнего меню на обоих языках.
_MENU_KEYS = (
    "menu_creator_panel", "menu_back_main", "menu_my_profile", "menu_add_work",
    "menu_portfolio", "menu_creator_orders", "menu_upload_review", "menu_order_service",
    "menu_settings", "menu_become_creator", "menu_application_pending", "menu_my_orders",
    "menu_reviews",
)
MENU_BUTTONS = frozenset(
    [t(key, lang) for key in _MENU_KEYS for lang in Lang]
    + [c.ru for c in CATEGORIES] + [c.en for c in CATEGORIES]
)


def _match(text: str, key: str) -> bool:
    """Сопоставление кнопки независимо от языка интерфейса."""
    return text in (t(key, Lang.ru), t(key, Lang.en))


async def _require_creator(message: Message, session: AsyncSession, user: User):
    """Гард исполнительских кнопок: возвращает Creator или None (+сообщение)."""
    creator = await get_approved_creator(session, user.id)
    if creator is None:
        await message.answer(t("profile_only_creator", user.lang))
    return creator


@nav_router.message(~StateFilter(None), F.text.in_(MENU_BUTTONS))
async def menu_button_in_form(
    message: Message, state: FSMContext, session: AsyncSession, user: User | None
):
    """Кнопка нижнего меню посреди пошаговой формы: форму бросаем, кнопку выполняем.

    Иначе подпись кнопки записалась бы ответом на текущий шаг («📁 Мои заказы»
    в поле «Жанр»), а в шагах без «Отмены» человек вообще не мог выйти.
    """
    await state.clear()
    await menu_router(message, state, session, user)


@router.message()
async def menu_router(
    message: Message, state: FSMContext, session: AsyncSession, user: User | None
):
    if user is None or user.role is None:
        # Без регистрации бот раньше молчал — человек не понимал, что делать.
        await message.answer(t("need_start", user.lang if user else Lang.ru))
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
        status = await profiles_repo.menu_status(session, user.id)
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
        await start_creator_application(message, state, session, user, message.from_user.username)
        return
    if _match(text, "menu_application_pending"):
        status = await profiles_repo.menu_status(session, user.id)
        if status == CreatorStatus.approved:
            await message.answer(t("creator_already_approved", user.lang))
        elif status == CreatorStatus.blocked:
            await message.answer(t("creator_blocked_info", user.lang),
                                 reply_markup=main_menu(user.lang, status))
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
        return
    if _match(text, "menu_reviews"):
        await open_reviews(message, state, session, user)
        return

    # Ничего не подошло (свободный текст, стикер, пропала клавиатура) —
    # объясняем и возвращаем меню вместо молчания.
    await message.answer(
        t("unknown_input", user.lang),
        reply_markup=main_menu(user.lang, await profiles_repo.menu_status(session, user.id)),
    )


@router.callback_query()
async def outdated_button(call: CallbackQuery, user: User | None):
    """Кнопка, которую уже некому обработать (форма закрыта, раздел открыт заново).
    Без ответа у пользователя бесконечно крутятся часики на кнопке."""
    await call.answer(t("button_outdated", user.lang if user else Lang.ru))
