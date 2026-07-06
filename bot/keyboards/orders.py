from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.db.models import Lang
from bot.locales import t


def take_order_keyboard(lang: Lang, order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t("btn_take_order", lang), callback_data=f"ordtake:{order_id}")]
        ]
    )


def client_confirm_keyboard(lang: Lang, order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t("btn_confirm_creator", lang), callback_data=f"ordclient:confirm:{order_id}")],
            [InlineKeyboardButton(text=t("btn_cancel_order", lang), callback_data=f"ordclient:cancel:{order_id}")],
        ]
    )


def client_cancel_keyboard(lang: Lang, order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t("btn_cancel_order", lang), callback_data=f"ordclient:cancel:{order_id}")]
        ]
    )


def admin_prepay_keyboard(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t("btn_confirm_prepay", Lang.ru), callback_data=f"ordadmin:prepay:{order_id}")]
        ]
    )


def admin_final_keyboard(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t("btn_confirm_final", Lang.ru), callback_data=f"ordadmin:final:{order_id}")]
        ]
    )
