"""Утилиты показа карточек с медиа.

Telegram не даёт «превратить» текстовое сообщение в медиа-сообщение
редактированием (editMessageMedia работает только если медиа уже есть).
Поэтому переход текст↔фото делаем удалением текущего сообщения и отправкой
нового. Медиа и кнопки всегда в одном сообщении → кнопки не «улетают».
"""
from aiogram.types import CallbackQuery, InlineKeyboardMarkup


async def replace_card(
    call: CallbackQuery,
    text: str,
    kb: InlineKeyboardMarkup | None = None,
    photo: str | None = None,
) -> None:
    """Заменяет текущее сообщение карточкой (фото+подпись+кнопки или текст)."""
    try:
        await call.message.delete()
    except Exception:
        pass
    if photo:
        await call.message.answer_photo(photo, caption=text, reply_markup=kb)
    else:
        await call.message.answer(text, reply_markup=kb)
