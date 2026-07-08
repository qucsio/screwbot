from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.db.models import Lang
from bot.locales import t


def take_order_keyboard(lang: Lang, order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t("btn_take_order", lang), callback_data=f"ordtake:{order_id}")]
        ]
    )
