from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup

from bot.config import get_settings

settings = get_settings()


async def send_to_moderation(
    bot: Bot,
    text: str,
    markup: InlineKeyboardMarkup | None = None,
) -> None:
    """Постит в топик модерации супергруппы; фолбэк — в личку админу."""
    if settings.group_id and settings.moderation_thread_id:
        await bot.send_message(
            settings.group_id,
            text,
            message_thread_id=settings.moderation_thread_id,
            reply_markup=markup,
        )
    else:
        await bot.send_message(settings.admin_id, text, reply_markup=markup)


async def notify_admin(bot: Bot, text: str, markup: InlineKeyboardMarkup | None = None) -> None:
    """Личное уведомление админу (вопросы/заявки на покупку)."""
    await bot.send_message(settings.admin_id, text, reply_markup=markup)
