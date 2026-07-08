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
    audio_file_id: str | None = None,
) -> None:
    """Карточка работы на модерацию: обложка+подпись+кнопки, для бита ещё аудио."""
    if cover_file_id:
        await bot.send_photo(app_config.ADMIN_ID, cover_file_id, caption=caption, reply_markup=markup)
    else:
        await bot.send_message(app_config.ADMIN_ID, caption, reply_markup=markup)
    if audio_file_id:
        await bot.send_audio(app_config.ADMIN_ID, audio_file_id)


async def notify_admin(bot: Bot, text: str, markup: InlineKeyboardMarkup | None = None) -> None:
    """Личное уведомление админу (вопросы/заявки на покупку)."""
    await bot.send_message(app_config.ADMIN_ID, text, reply_markup=markup)
