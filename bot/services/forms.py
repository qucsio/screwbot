"""Каркас пошаговых форм: единый заголовок шага, кнопка отмены, type-guards.

Проблема, которую решает: раньше текстовые шаги делали ``message.text.strip()``
и падали, если пользователь присылал файл; об отмене нужно было угадывать команду
``/cancel``; пользователь не видел, на каком он шаге.

Использование в хендлере:
    await message.answer(step(1, 3, "addbeat_title", lang), reply_markup=cancel_kb(lang))
    ...
    value = guard_text(message)
    if value is None:
        await message.answer(t("need_text", user.lang), reply_markup=cancel_kb(user.lang))
        return
"""
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import Lang, User
from bot.locales import t

router = Router()


def cancel_kb(lang: Lang) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t("form_cancel", lang), callback_data="form_cancel")]
        ]
    )


def step(idx: int, total: int, body_key: str, lang: Lang, **kw) -> str:
    """«Шаг N/M» + текст подсказки шага (body_key — ключ локали)."""
    return f"{t('form_step', lang, n=idx, total=total)}\n{t(body_key, lang, **kw)}"


def step_text(idx: int, total: int, body: str, lang: Lang) -> str:
    """«Шаг N/M» + уже готовый текст подсказки (не ключ локали)."""
    return f"{t('form_step', lang, n=idx, total=total)}\n{body}"


def guard_text(message: Message) -> str | None:
    """Непустой текст или None (файл/пустое сообщение не роняют форму)."""
    txt = message.text
    if txt is None or not txt.strip():
        return None
    return txt.strip()


@router.callback_query(F.data == "form_cancel")
async def form_cancel(
    call: CallbackQuery, state: FSMContext, session: AsyncSession, user: User | None
):
    await state.clear()
    from bot.db.models import CreatorStatus
    from bot.db.repositories.works import get_creator
    from bot.keyboards.common import creator_panel, main_menu

    lang = user.lang if user else Lang.ru
    markup = None
    if user and user.role:
        creator = await get_creator(session, user.id)
        status = creator.status if creator else None
        # Одобренный исполнитель возвращается в свою панель, остальные — в главное меню.
        markup = creator_panel(lang) if status == CreatorStatus.approved else main_menu(lang, status)
    await call.message.answer(t("cancelled", lang), reply_markup=markup)
    await call.answer()
