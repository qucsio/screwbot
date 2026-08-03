from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup

from bot import app_config


async def send_to_moderation(
    bot: Bot,
    text: str,
    markup: InlineKeyboardMarkup | None = None,
) -> None:
    """Модерация идёт в ЛС главного админа (отдельного чата модерации нет)."""
    await bot.send_message(app_config.ADMIN_ID, text, reply_markup=markup)


async def send_work_to_moderation(
    bot: Bot,
    caption: str,
    cover_file_id: str | None,
    markup: InlineKeyboardMarkup | None = None,
    media_type: str = "photo",
) -> None:
    """Карточка работы на модерацию: медиа+подпись+кнопки в одном сообщении."""
    if not cover_file_id:
        await bot.send_message(app_config.ADMIN_ID, caption, reply_markup=markup)
    elif media_type == "video":
        await bot.send_video(app_config.ADMIN_ID, cover_file_id, caption=caption, reply_markup=markup)
    else:
        await bot.send_photo(app_config.ADMIN_ID, cover_file_id, caption=caption, reply_markup=markup)


async def notify_admin(bot: Bot, text: str, markup: InlineKeyboardMarkup | None = None) -> None:
    """Личное уведомление админу (вопросы/заявки на покупку)."""
    await bot.send_message(app_config.ADMIN_ID, text, reply_markup=markup)
