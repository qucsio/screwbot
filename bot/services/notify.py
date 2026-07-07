from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup

from bot import app_config


async def send_to_moderation(
    bot: Bot,
    text: str,
    markup: InlineKeyboardMarkup | None = None,
) -> None:
    """Постит в топик модерации супергруппы; фолбэк — в личку админу."""
    if app_config.GROUP_ID and app_config.MODERATION_THREAD_ID:
        await bot.send_message(
            app_config.GROUP_ID,
            text,
            message_thread_id=app_config.MODERATION_THREAD_ID,
            reply_markup=markup,
        )
    else:
        await bot.send_message(app_config.ADMIN_ID, text, reply_markup=markup)


async def notify_admin(bot: Bot, text: str, markup: InlineKeyboardMarkup | None = None) -> None:
    """Личное уведомление админу (вопросы/заявки на покупку)."""
    await bot.send_message(app_config.ADMIN_ID, text, reply_markup=markup)
