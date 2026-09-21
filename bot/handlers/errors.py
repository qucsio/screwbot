"""Последний рубеж: необработанная ошибка в обработчике.

Без этого пользователь видит «зависшую» кнопку или просто тишину. Здесь только
лог и ответ пользователю; уведомлять ли админа — отдельное решение.
"""
import logging

from aiogram import Router
from aiogram.types import ErrorEvent

from bot.services.notify import safe_send

logger = logging.getLogger(__name__)
router = Router()

# Язык пользователя тут не узнать: сессия БД могла упасть вместе с обработчиком.
ERROR_TEXT = "⚠️ Что-то пошло не так, попробуйте ещё раз.\nSomething went wrong, please try again."


@router.errors()
async def on_error(event: ErrorEvent) -> bool:
    logger.error("Ошибка при обработке апдейта %s", event.update.update_id, exc_info=event.exception)
    update = event.update
    if update.callback_query:
        await safe_send(update.callback_query.answer(ERROR_TEXT, show_alert=True))
    elif update.message and update.message.chat.type == "private":
        await safe_send(update.message.answer(ERROR_TEXT))
    return True
