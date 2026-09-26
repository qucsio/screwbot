from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import Creator, CreatorProfile, ModerationStatus, User
from bot.db.repositories import orders as orders_repo
from bot.db.repositories import portfolio as portfolio_repo
from bot.db.repositories import profiles as profiles_repo
from bot.db.repositories import works as repo
from bot.locales import t
from bot.services.forms import cancel_kb, read_text
from bot.services.moderation import direction_title
from bot.services.money import fmt_money as _money
from bot.services.money import parse_money
from bot.services.text import EXPERIENCE_MAX, PORTFOLIO_LINKS_MAX, SOCIALS_MAX, esc
from bot.services.ui import replace_card
from bot.states.profile import ProfileEdit

router = Router()


def _status_text(status: ModerationStatus, lang) -> str:
    return t(f"status_{status.value}", lang)


def _cstatus(profile: CreatorProfile, lang) -> str:
    return t(f"cstatus_{profile.status.value}", lang)


async def _get_creator(session: AsyncSession, user: User) -> Creator | None:
    return await repo.get_approved_creator(session, user.id)


# =========================================================================
# КАБИНЕТ: человек и его направления
# =========================================================================


def _cabinet_keyboard(profiles: list[CreatorProfile], lang) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(
            text=f"{direction_title(p.direction, lang)} · {_cstatus(p, lang)}",
            callback_data=f"prof:p:{p.id}",
        )]
        for p in profiles
    ]
    rows.append([InlineKeyboardButton(text=t("btn_add_direction", lang), callback_data="prof:adddir")])
    rows.append([
        InlineKeyboardButton(text=t("btn_edit_socials", lang), callback_data="prof:socials"),
        InlineKeyboardButton(text=t("btn_my_works", lang), callback_data="prof:works"),
    ])
    rows.append([InlineKeyboardButton(text=t("addwork_choose", lang), callback_data="prof:addwork")])
    rows.append([InlineKeyboardButton(text=t("btn_delete_profile", lang), callback_data="prof:delete")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _cabinet(session: AsyncSession, creator: Creator, lang) -> tuple[str, InlineKeyboardMarkup]:
    profiles = await profiles_repo.list_profiles(session, creator.id)
    works = await repo.list_creator_works(session, creator.id)
    media = await portfolio_repo.count(session, creator.id)
    text = t(
        "profile_title", lang,
        socials=esc(creator.socials, limit=SOCIALS_MAX), balance=_money(creator.balance),
    )
    text += "\n\n" + t("profile_counts", lang, works=len(works), media=media)
    return text, _cabinet_keyboard(profiles, lang)


async def open_profile(message: Message, session: AsyncSession, user: User):
    creator = await _get_creator(session, user)
    if creator is None:
        await message.answer(t("profile_only_creator", user.lang))
        return
    text, kb = await _cabinet(session, creator, user.lang)
    await message.answer(text, reply_markup=kb)


@router.message(Command("profile"))
async def cmd_profile(message: Message, session: AsyncSession, user: User | None):
    if user is None:
        return
    await open_profile(message, session, user)


@router.callback_query(F.data == "prof:root")
async def profile_root(call: CallbackQuery, session: AsyncSession, user: User):
    creator = await _get_creator(session, user)
    if creator is None:
        await call.answer()
        return
    text, kb = await _cabinet(session, creator, user.lang)
    await replace_card(call, text, kb)
    await call.answer()


@router.callback_query(F.data == "prof:adddir")
async def profile_add_direction(call: CallbackQuery, state: FSMContext, session: AsyncSession, user: User):
    """Ещё одно направление — та же заявка, что и «Стать исполнителем»."""
    from bot.handlers.start import start_creator_application

    await start_creator_application(call.message, state, session, user, call.from_user.username)
    await call.answer()


@router.callback_query(F.data == "prof:addwork")
async def profile_addwork(call: CallbackQuery, session: AsyncSession, user: User):
    from bot.handlers.beats import _add_work_keyboard

    await call.message.answer(t("addwork_choose", user.lang), reply_markup=_add_work_keyboard(user.lang))
    await call.answer()


# --- Карточка направления -------------------------------------------------


def _profile_keyboard(profile: CreatorProfile, lang) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=t("btn_edit_desc", lang), callback_data=f"prof:pf:about:{profile.id}"),
            InlineKeyboardButton(text=t("btn_edit_links", lang), callback_data=f"prof:pf:links:{profile.id}"),
        ],
        [InlineKeyboardButton(text=t("btn_view_portfolio", lang), callback_data=f"port:open:{profile.id}")],
        [InlineKeyboardButton(text=t("back", lang), callback_data="prof:root")],
    ])


def _profile_text(profile: CreatorProfile, lang) -> str:
    return t(
        "profile_direction_card", lang,
        direction=direction_title(profile.direction, lang),
        status=_cstatus(profile, lang),
        about=esc(profile.about, limit=EXPERIENCE_MAX),
        links=esc(profile.links, limit=PORTFOLIO_LINKS_MAX),
    )


async def _own_profile(session: AsyncSession, user: User, profile_id: int) -> CreatorProfile | None:
    creator = await repo.get_creator(session, user.id)
    return await profiles_repo.get_own_profile(session, profile_id, creator.id) if creator else None


@router.callback_query(F.data.startswith("prof:p:"))
async def open_direction_profile(call: CallbackQuery, session: AsyncSession, user: User):
    profile = await _own_profile(session, user, int(call.data.split(":")[2]))
    if profile is None:
        await call.answer(t("button_outdated", user.lang))
        return
    await replace_card(call, _profile_text(profile, user.lang), _profile_keyboard(profile, user.lang))
    await call.answer()


@router.callback_query(F.data.startswith("prof:pf:"))
async def edit_profile_field(call: CallbackQuery, state: FSMContext, session: AsyncSession, user: User):
    _, _, field, profile_id_raw = call.data.split(":")
    profile = await _own_profile(session, user, int(profile_id_raw))
    if profile is None:
        await call.answer(t("button_outdated", user.lang))
        return
    await state.set_state(ProfileEdit.about if field == "about" else ProfileEdit.links)
    await state.update_data(profile_id=profile.id)
    await call.message.answer(
        t("profile_ask_desc" if field == "about" else "profile_ask_links", user.lang),
        reply_markup=cancel_kb(user.lang),
    )
    await call.answer()


async def _save_profile_field(message: Message, state: FSMContext, session: AsyncSession,
                              user: User, field: str, max_len: int) -> None:
    value = await read_text(message, user.lang, max_len)
    if value is None:
        return
    data = await state.get_data()
    await state.clear()
    profile = await _own_profile(session, user, data["profile_id"])
    if profile is None:
        return
    setattr(profile, field, value)
    await session.commit()
    await message.answer(t("profile_saved", user.lang))
    await message.answer(_profile_text(profile, user.lang), reply_markup=_profile_keyboard(profile, user.lang))


@router.message(ProfileEdit.about)
async def save_about(message: Message, state: FSMContext, session: AsyncSession, user: User):
    await _save_profile_field(message, state, session, user, "about", EXPERIENCE_MAX)


@router.message(ProfileEdit.links)
async def save_links(message: Message, state: FSMContext, session: AsyncSession, user: User):
    await _save_profile_field(message, state, session, user, "links", PORTFOLIO_LINKS_MAX)


# --- Соцсети: общие для человека, а не для направления --------------------


@router.callback_query(F.data == "prof:socials")
async def edit_socials(call: CallbackQuery, state: FSMContext, user: User):
    await state.set_state(ProfileEdit.socials)
    await call.message.answer(t("profile_ask_socials", user.lang), reply_markup=cancel_kb(user.lang))
    await call.answer()


@router.message(ProfileEdit.socials)
async def save_socials(message: Message, state: FSMContext, session: AsyncSession, user: User):
    value = await read_text(message, user.lang, SOCIALS_MAX)
    if value is None:
        return
    creator = await _get_creator(session, user)
    if creator is None:
        return
    creator.socials = value
    await session.commit()
    await state.clear()
    await message.answer(t("profile_saved", user.lang))
    text, kb = await _cabinet(session, creator, user.lang)
    await message.answer(text, reply_markup=kb)


# --- Мои работы (CRUD) ---------------------------------------------------


def _works_keyboard(works, lang) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=w.title, callback_data=f"prof:work:{w.id}")] for w in works]
    rows.append([InlineKeyboardButton(text=t("back", lang), callback_data="prof:root")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _work_keyboard(work_id: int, lang, has_audio: bool = False, ctype: str = "beat") -> InlineKeyboardMarkup:
    if ctype in ("visual", "video"):
        # у визуала/видео нет аренды/аудио — только цена выкупа
        rows = [[InlineKeyboardButton(text=t("btn_price_buy", lang), callback_data=f"prof:price:buy:{work_id}")]]
    else:
        rows = [
            [
                InlineKeyboardButton(text=t("btn_price_rent", lang), callback_data=f"prof:price:rent:{work_id}"),
                InlineKeyboardButton(text=t("btn_price_buy", lang), callback_data=f"prof:price:buy:{work_id}"),
            ],
        ]
        if has_audio:
            rows.append([InlineKeyboardButton(text=t("beat_listen", lang), callback_data=f"beat:listen:{work_id}")])
    rows.append([InlineKeyboardButton(text=t("btn_delete_work", lang), callback_data=f"prof:del:{work_id}")])
    rows.append([InlineKeyboardButton(text=t("back", lang), callback_data="prof:works")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _work_text(work, lang, ctype: str = "beat") -> str:
    if ctype in ("visual", "video"):
        return t(
            "work_detail_video" if ctype == "video" else "work_detail_visual", lang,
            title=esc(work.title), vtype=esc(work.genre),
            buy=_money(work.price_buy),
            status=_status_text(work.moderation_status, lang),
        )
    return t(
        "work_detail", lang,
        title=esc(work.title), genre=esc(work.genre), key=esc(work.key), bpm=work.bpm or "—",
        rent=_money(work.price_rent), buy=_money(work.price_buy),
        status=_status_text(work.moderation_status, lang),
    )


async def _show_works(call: CallbackQuery, session: AsyncSession, creator: Creator, user: User):
    works = await repo.list_creator_works(session, creator.id)
    if works:
        await replace_card(call, t("works_list_title", user.lang), _works_keyboard(works, user.lang))
        return
    text, kb = await _cabinet(session, creator, user.lang)
    await replace_card(call, t("works_empty", user.lang) + "\n\n" + text, kb)


@router.callback_query(F.data == "prof:works")
async def my_works(call: CallbackQuery, session: AsyncSession, user: User):
    creator = await _get_creator(session, user)
    if creator is None:
        await call.answer()
        return
    await _show_works(call, session, creator, user)
    await call.answer()


@router.callback_query(F.data.startswith("prof:work:"))
async def open_work(call: CallbackQuery, session: AsyncSession, user: User):
    work_id = int(call.data.split(":")[2])
    creator = await _get_creator(session, user)
    work = await repo.get_creator_work(session, work_id, creator.id) if creator else None
    if work is None:
        await call.answer()
        return
    ctype = await repo.work_catalog_type(session, work)
    kb = _work_keyboard(work.id, user.lang, bool(work.audio_file_id), ctype)
    if ctype == "video":
        await replace_card(call, _work_text(work, user.lang, ctype), kb, video=work.cover_file_id)
    else:
        await replace_card(call, _work_text(work, user.lang, ctype), kb, photo=work.cover_file_id)
    await call.answer()


@router.callback_query(F.data.startswith("prof:del:"))
async def delete_work_ask(call: CallbackQuery, session: AsyncSession, user: User):
    """Удаление необратимо — сначала подтверждение прямо на карточке работы."""
    work_id = int(call.data.split(":")[2])
    creator = await _get_creator(session, user)
    work = await repo.get_creator_work(session, work_id, creator.id) if creator else None
    if work is None:
        await call.answer()
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("btn_delete_work_yes", user.lang), callback_data=f"prof:delok:{work.id}")],
        [InlineKeyboardButton(text=t("back", user.lang), callback_data=f"prof:work:{work.id}")],
    ])
    try:
        await call.message.edit_reply_markup(reply_markup=kb)
    except Exception:
        pass
    await call.answer(t("work_delete_confirm", user.lang))


@router.callback_query(F.data.startswith("prof:delok:"))
async def delete_work(call: CallbackQuery, session: AsyncSession, user: User):
    work_id = int(call.data.split(":")[2])
    creator = await _get_creator(session, user)
    work = await repo.get_creator_work(session, work_id, creator.id) if creator else None
    if work is None:
        await call.answer()
        return
    await session.delete(work)
    await session.commit()
    await call.answer(t("work_deleted", user.lang), show_alert=True)
    await _show_works(call, session, creator, user)


@router.callback_query(F.data.startswith("prof:price:"))
async def ask_price(call: CallbackQuery, state: FSMContext, session: AsyncSession, user: User):
    _, _, kind, work_id_raw = call.data.split(":")
    creator = await _get_creator(session, user)
    work = await repo.get_creator_work(session, int(work_id_raw), creator.id) if creator else None
    if work is None:
        await call.answer()
        return
    await state.set_state(ProfileEdit.price)
    await state.update_data(
        work_id=work.id, price_kind=kind,
        card_chat=call.message.chat.id, card_msg=call.message.message_id,
    )
    await call.message.answer(t("work_ask_price", user.lang), reply_markup=cancel_kb(user.lang))
    await call.answer()


@router.message(ProfileEdit.price)
async def save_price(message: Message, state: FSMContext, session: AsyncSession, user: User, bot: Bot):
    price = parse_money(message.text, allow_zero=True)
    if price is None:
        await message.answer(t("work_price_invalid", user.lang), reply_markup=cancel_kb(user.lang))
        return
    data = await state.get_data()
    await state.clear()
    creator = await _get_creator(session, user)
    work = await repo.get_creator_work(session, data["work_id"], creator.id) if creator else None
    if work is None:
        return
    if data["price_kind"] == "rent":
        work.price_rent = price
    else:
        work.price_buy = price
    await session.commit()
    # обновляем подпись карточки-фото на месте
    if data.get("card_msg"):
        ctype = await repo.work_catalog_type(session, work)
        kb = _work_keyboard(work.id, user.lang, bool(work.audio_file_id), ctype)
        try:
            await bot.edit_message_caption(
                chat_id=data["card_chat"], message_id=data["card_msg"],
                caption=_work_text(work, user.lang, ctype), reply_markup=kb,
            )
        except Exception:
            pass
    await message.answer(t("work_price_updated", user.lang))


# --- Удаление своего профиля исполнителем --------------------------------


def _delete_confirm_kb(lang) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t("btn_delete_profile_yes", lang), callback_data="prof:delete:yes")],
            [InlineKeyboardButton(text=t("back", lang), callback_data="prof:root")],
        ]
    )


@router.callback_query(F.data == "prof:delete")
async def profile_delete_ask(call: CallbackQuery, session: AsyncSession, user: User):
    """Перед удалением показываем, что именно потеряется, и не даём бросить заказы."""
    creator = await _get_creator(session, user)
    if creator is None:
        await call.answer()
        return
    active = await orders_repo.active_ids_for_creator(session, creator.id)
    if active:
        await call.message.answer(
            t("profile_delete_active_orders", user.lang, orders=", ".join(f"#{i}" for i in active))
        )
        await call.answer()
        return
    profiles = await profiles_repo.list_profiles(session, creator.id)
    works = await repo.list_creator_works(session, creator.id)
    media = await portfolio_repo.count(session, creator.id)
    text = t(
        "profile_delete_confirm", user.lang,
        directions=len(profiles), works=len(works), media=media,
    )
    if creator.balance and creator.balance > 0:
        text += "\n\n" + t("profile_delete_balance", user.lang, balance=_money(creator.balance))
    await call.message.answer(text, reply_markup=_delete_confirm_kb(user.lang))
    await call.answer()


@router.callback_query(F.data == "prof:delete:yes")
async def profile_delete_do(call: CallbackQuery, session: AsyncSession, user: User):
    from sqlalchemy import update

    from bot.db.models import Order
    from bot.keyboards.common import main_menu

    creator = await _get_creator(session, user)
    if creator is None:
        await call.answer()
        return
    # отвязываем от заказов (FK без ON DELETE); профили, работы и портфолио уйдут каскадом
    await session.execute(update(Order).where(Order.creator_id == creator.id).values(creator_id=None))
    await session.delete(creator)
    await session.commit()
    await call.answer(t("profile_deleted", user.lang), show_alert=True)
    # исполнитель снова просто клиент — возвращаем базовое меню
    await call.message.answer(t("main_menu", user.lang), reply_markup=main_menu(user.lang, None))
