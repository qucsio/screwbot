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
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    ReplyKeyboardMarkup,
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


def skip_kb(lang: Lang, skip_data: str) -> InlineKeyboardMarkup:
    """«Пропустить» + «Отмена» для необязательного шага (вместо «наберите -»)."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t("form_skip", lang), callback_data=skip_data)],
            [InlineKeyboardButton(text=t("form_cancel", lang), callback_data="form_cancel")],
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


async def read_text(
    message: Message,
    lang: Lang,
    max_len: int,
    need_key: str = "need_text",
    too_long_key: str = "text_too_long",
) -> str | None:
    """Текст шага с проверкой длины или None — пользователю уже ответили, что не так.

    Длина ограничена, чтобы итоговое сообщение (тендер, карточка, подпись к медиа)
    влезло в лимиты Telegram — иначе оно просто не отправится.
    """
    value = guard_text(message)
    if value is None:
        await message.answer(t(need_key, lang), reply_markup=cancel_kb(lang))
        return None
    if len(value) > max_len:
        await message.answer(
            t(too_long_key, lang, length=len(value), limit=max_len),
            reply_markup=cancel_kb(lang),
        )
        return None
    return value


async def _menu_after_cancel(session: AsyncSession, user: User | None) -> ReplyKeyboardMarkup | None:
    from bot.db.models import CreatorStatus
    from bot.db.repositories.works import get_creator
    from bot.keyboards.common import creator_panel, main_menu

    if not (user and user.role):
        return None
    creator = await get_creator(session, user.id)
    status = creator.status if creator else None
    # Одобренный исполнитель возвращается в свою панель, остальные — в главное меню.
    return creator_panel(user.lang) if status == CreatorStatus.approved else main_menu(user.lang, status)


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext, session: AsyncSession, user: User | None):
    """/cancel в любом состоянии. Роутер подключён раньше админского — иначе
    в админских вводах «/cancel» принимался бы за сумму или новое значение поля."""
    await state.clear()
    lang = user.lang if user else Lang.ru
    await message.answer(t("cancelled", lang), reply_markup=await _menu_after_cancel(session, user))


@router.callback_query(F.data == "form_cancel")
async def form_cancel(
    call: CallbackQuery, state: FSMContext, session: AsyncSession, user: User | None
):
    await state.clear()
    lang = user.lang if user else Lang.ru
    await call.message.answer(t("cancelled", lang), reply_markup=await _menu_after_cancel(session, user))
    await call.answer()
