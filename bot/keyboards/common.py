from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
)

from bot.db.models import Lang
from bot.locales import t


def lang_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang:ru"),
                InlineKeyboardButton(text="🇬🇧 English", callback_data="lang:en"),
            ]
        ]
    )


def role_keyboard(lang: Lang) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t("role_client", lang), callback_data="role:client")],
            [InlineKeyboardButton(text=t("role_creator", lang), callback_data="role:creator")],
        ]
    )


def main_menu(lang: Lang) -> ReplyKeyboardMarkup:
    from bot.categories import CATEGORIES

    # кнопки категорий из реестра + «Отзывы» в конце
    titles = [c.title(lang) for c in CATEGORIES] + [t("menu_reviews", lang)]
    rows, row = [], []
    for i, title in enumerate(titles, 1):
        row.append(KeyboardButton(text=title))
        if i % 2 == 0:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def work_moderation_keyboard(lang: Lang, work_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t("mod_approve", lang), callback_data=f"modwork:approve:{work_id}"
                ),
                InlineKeyboardButton(
                    text=t("mod_reject", lang), callback_data=f"modwork:reject:{work_id}"
                ),
            ]
        ]
    )


def filter_intro_keyboard(lang: Lang) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t("filter_all", lang), callback_data="beatflt:all")],
            [InlineKeyboardButton(text=t("filter_setup", lang), callback_data="beatflt:setup")],
        ]
    )


def genre_keyboard(lang: Lang, genres: list[str]) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=g, callback_data=f"fltgenre:{g}")] for g in genres]
    rows.append([InlineKeyboardButton(text=t("filter_any", lang), callback_data="fltgenre:__any__")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def beat_card_keyboard(lang: Lang, work_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=t("beat_prev", lang), callback_data="beatnav:prev"),
                InlineKeyboardButton(text=t("beat_listen", lang), callback_data=f"beat:listen:{work_id}"),
                InlineKeyboardButton(text=t("beat_next", lang), callback_data="beatnav:next"),
            ],
            [
                InlineKeyboardButton(text=t("beat_buy", lang), callback_data=f"beat:buy:{work_id}"),
                InlineKeyboardButton(text=t("beat_ask", lang), callback_data=f"beat:ask:{work_id}"),
            ],
        ]
    )


def moderation_keyboard(lang: Lang, creator_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t("mod_approve", lang), callback_data=f"modcreator:approve:{creator_id}"
                ),
                InlineKeyboardButton(
                    text=t("mod_reject", lang), callback_data=f"modcreator:reject:{creator_id}"
                ),
            ]
        ]
    )
