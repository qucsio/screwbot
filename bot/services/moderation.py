"""Карточки модерации (заявка исполнителя, новая работа).

Общие для уведомления админу и для очереди «На модерации» в админ-панели:
одна и та же карточка, одни и те же кнопки.
"""
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup

from bot.categories import direction_by_code
from bot.db.models import CreatorProfile, Lang, User, Work
from bot.keyboards.common import profile_moderation_keyboard, work_moderation_keyboard
from bot.locales import t
from bot.services.money import fmt_money
from bot.services.notify import send_to_moderation, send_work_to_moderation
from bot.services.order_view import contact
from bot.services.text import EXPERIENCE_MAX, PORTFOLIO_LINKS_MAX, esc


def direction_title(code: str, lang: Lang = Lang.ru) -> str:
    direction = direction_by_code(code)
    return direction.title(lang) if direction else code


def profile_card(user: User, profile: CreatorProfile) -> tuple[str, InlineKeyboardMarkup]:
    text = t(
        "mod_new_profile", Lang.ru,
        direction=direction_title(profile.direction),
        contact=contact(user),
        nickname=esc(user.nickname),
        about=esc(profile.about, limit=EXPERIENCE_MAX),
        links=esc(profile.links, limit=PORTFOLIO_LINKS_MAX),
    )
    return text, profile_moderation_keyboard(Lang.ru, profile.id, profile.creator_id)


def work_card(work: Work, author: User, ctype: str) -> tuple[str, InlineKeyboardMarkup]:
    """Подпись и кнопки карточки работы (ctype: beat | visual | video)."""
    if ctype in ("visual", "video"):
        text = t(
            "mod_new_video" if ctype == "video" else "mod_new_visual", Lang.ru,
            author=contact(author), title=esc(work.title),
            vtype=esc(work.genre), buy=fmt_money(work.price_buy),
        )
    else:
        text = t(
            "mod_new_beat", Lang.ru,
            author=contact(author), title=esc(work.title),
            genre=esc(work.genre), key=esc(work.key), bpm=work.bpm or "—",
            rent=fmt_money(work.price_rent), buy=fmt_money(work.price_buy),
        )
    kb = work_moderation_keyboard(Lang.ru, work.id, work.creator_id, has_audio=bool(work.audio_file_id))
    return text, kb


async def send_profile_card(bot: Bot, user: User, profile: CreatorProfile) -> None:
    text, kb = profile_card(user, profile)
    await send_to_moderation(bot, text, kb)


async def send_work_card(bot: Bot, work: Work, author: User, ctype: str) -> None:
    text, kb = work_card(work, author, ctype)
    await send_work_to_moderation(
        bot, text, work.cover_file_id, kb, media_type="video" if ctype == "video" else "photo",
    )
