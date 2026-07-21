from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
)

from bot.db.models import CreatorStatus, Lang
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


def settings_lang_keyboard() -> InlineKeyboardMarkup:
    """Смена языка после регистрации (префикс setlang: — вне состояния регистрации)."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🇷🇺 Русский", callback_data="setlang:ru"),
                InlineKeyboardButton(text="🇬🇧 English", callback_data="setlang:en"),
            ]
        ]
    )


def _build_keyboard(titles: list[str]) -> ReplyKeyboardMarkup:
    rows, row = [], []
    for i, title in enumerate(titles, 1):
        row.append(KeyboardButton(text=title))
        if i % 2 == 0:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def main_menu(lang: Lang, creator_status: CreatorStatus | None = None) -> ReplyKeyboardMarkup:
    """Базовое меню пользователя. Последняя кнопка зависит от статуса исполнителя.

    Каждый пользователь — клиент. В корне только каталоги готовых работ + вход в
    подменю услуг «на заказ», чтобы меню не разрасталось. Исполнитель получает
    вход в отдельную панель (creator_panel), а не свалку кнопок.
    """
    from bot.categories import catalog_categories

    titles = [c.title(lang) for c in catalog_categories()] + [
        t("menu_order_service", lang),
        t("menu_my_orders", lang),
        t("menu_reviews", lang),
        t("menu_settings", lang),
    ]
    if creator_status == CreatorStatus.approved:
        titles.append(t("menu_creator_panel", lang))
    elif creator_status == CreatorStatus.pending:
        titles.append(t("menu_application_pending", lang))
    else:
        titles.append(t("menu_become_creator", lang))
    return _build_keyboard(titles)


def order_menu(lang: Lang) -> ReplyKeyboardMarkup:
    """Подменю услуг «на заказ» (формы ТЗ)."""
    from bot.categories import custom_categories

    titles = [c.title(lang) for c in custom_categories()] + [t("menu_back_main", lang)]
    return _build_keyboard(titles)


def creator_panel(lang: Lang) -> ReplyKeyboardMarkup:
    """Отдельная панель одобренного исполнителя."""
    titles = [
        t("menu_my_profile", lang),
        t("menu_add_work", lang),
        t("menu_portfolio", lang),
        t("menu_creator_orders", lang),
        t("menu_upload_review", lang),
        t("menu_back_main", lang),
    ]
    return _build_keyboard(titles)


def work_moderation_keyboard(
    lang: Lang, work_id: int, creator_id: int, has_audio: bool = False
) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text=t("mod_approve", lang), callback_data=f"modwork:approve:{work_id}"),
            InlineKeyboardButton(text=t("mod_reject", lang), callback_data=f"modwork:reject:{work_id}"),
        ],
    ]
    if has_audio:
        rows.append([InlineKeyboardButton(text=t("beat_listen", lang), callback_data=f"beat:listen:{work_id}")])
    rows.append([InlineKeyboardButton(text=t("mod_author_profile", lang), callback_data=f"modauthor:{creator_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


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


def work_card_keyboard(lang: Lang, work_id: int, catalog_type: str) -> InlineKeyboardMarkup:
    nav = [InlineKeyboardButton(text=t("beat_prev", lang), callback_data="beatnav:prev")]
    if catalog_type == "beat":
        nav.append(InlineKeyboardButton(text=t("beat_listen", lang), callback_data=f"beat:listen:{work_id}"))
    nav.append(InlineKeyboardButton(text=t("beat_next", lang), callback_data="beatnav:next"))
    return InlineKeyboardMarkup(
        inline_keyboard=[
            nav,
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
            ],
            [InlineKeyboardButton(text=t("btn_view_portfolio", lang), callback_data=f"pfopen:{creator_id}")],
        ]
    )
