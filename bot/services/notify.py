import logging
from collections.abc import Awaitable
from typing import TypeVar

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import InlineKeyboardMarkup

from bot import app_config

logger = logging.getLogger(__name__)

T = TypeVar("T")


async def safe_send(call: Awaitable[T]) -> T | None:
    """Отправка, которая не роняет обработчик.

    Уведомления уходят уже после записи в БД. Если адресат заблокировал бота
    или недоступен, исключение оборвало бы цепочку: остальные участники не
    получили бы свои сообщения. Поэтому ошибка только логируется.
    """
    try:
        return await call
    except TelegramAPIError as e:
        logger.warning("Сообщение не доставлено: %s", e)
        return None


async def send_to_moderation(
    bot: Bot,
    text: str,
    markup: InlineKeyboardMarkup | None = None,
) -> None:
    """Модерация идёт в ЛС главного админа (отдельного чата модерации нет)."""
    await safe_send(bot.send_message(app_config.ADMIN_ID, text, reply_markup=markup))


async def send_work_to_moderation(
    bot: Bot,
    caption: str,
    cover_file_id: str | None,
    markup: InlineKeyboardMarkup | None = None,
    media_type: str = "photo",
) -> None:
    """Карточка работы на модерацию: медиа+подпись+кнопки в одном сообщении."""
    if not cover_file_id:
        await safe_send(bot.send_message(app_config.ADMIN_ID, caption, reply_markup=markup))
    elif media_type == "video":
        await safe_send(bot.send_video(app_config.ADMIN_ID, cover_file_id, caption=caption, reply_markup=markup))
    else:
        await safe_send(bot.send_photo(app_config.ADMIN_ID, cover_file_id, caption=caption, reply_markup=markup))


async def notify_admin(bot: Bot, text: str, markup: InlineKeyboardMarkup | None = None) -> None:
    """Личное уведомление админу (вопросы/заявки на покупку)."""
    await safe_send(bot.send_message(app_config.ADMIN_ID, text, reply_markup=markup))
