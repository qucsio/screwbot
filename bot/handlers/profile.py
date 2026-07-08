from decimal import Decimal, InvalidOperation

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import Creator, ModerationStatus, User
from bot.db.repositories import works as repo
from bot.locales import t
from bot.states.profile import ProfileEdit

router = Router()


def _money(v) -> str:
    return f"{v:g}" if v is not None else "—"


def _status_text(status: ModerationStatus, lang) -> str:
    return t(f"status_{status.value}", lang)


def _profile_keyboard(lang) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=t("btn_edit_socials", lang), callback_data="prof:socials"),
                InlineKeyboardButton(text=t("btn_edit_desc", lang), callback_data="prof:desc"),
            ],
            [InlineKeyboardButton(text=t("btn_my_works", lang), callback_data="prof:works")],
            [InlineKeyboardButton(text=t("addwork_choose", lang), callback_data="prof:addwork")],
        ]
    )


def _profile_text(creator: Creator, lang) -> str:
    return t(
        "profile_title", lang,
        service=creator.service or "—",
        socials=creator.socials or "—",
        desc=creator.experience or "—",
        balance=_money(creator.balance),
    )


async def _get_creator(session: AsyncSession, user: User) -> Creator | None:
    return await repo.get_approved_creator(session, user.id)


# =========================================================================


async def open_profile(message: Message, session: AsyncSession, user: User):
    creator = await _get_creator(session, user)
    if creator is None:
        await message.answer(t("profile_only_creator", user.lang))
        return
    await message.answer(_profile_text(creator, user.lang), reply_markup=_profile_keyboard(user.lang))


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
    await call.message.edit_text(_profile_text(creator, user.lang), reply_markup=_profile_keyboard(user.lang))
    await call.answer()


@router.callback_query(F.data == "prof:addwork")
async def profile_addwork(call: CallbackQuery, session: AsyncSession, user: User):
    from bot.handlers.beats import _add_work_keyboard

    await call.message.answer(t("addwork_choose", user.lang), reply_markup=_add_work_keyboard(user.lang))
    await call.answer()


# --- Правка соцсетей / описания ------------------------------------------


@router.callback_query(F.data == "prof:socials")
async def edit_socials(call: CallbackQuery, state: FSMContext, user: User):
    await state.set_state(ProfileEdit.socials)
    await call.message.answer(t("profile_ask_socials", user.lang))
    await call.answer()


@router.callback_query(F.data == "prof:desc")
async def edit_desc(call: CallbackQuery, state: FSMContext, user: User):
    await state.set_state(ProfileEdit.description)
    await call.message.answer(t("profile_ask_desc", user.lang))
    await call.answer()


@router.message(ProfileEdit.socials)
async def save_socials(message: Message, state: FSMContext, session: AsyncSession, user: User):
    creator = await _get_creator(session, user)
    if creator:
        creator.socials = (message.text or "").strip()
        await session.commit()
    await state.clear()
    await message.answer(t("profile_saved", user.lang))
    await message.answer(_profile_text(creator, user.lang), reply_markup=_profile_keyboard(user.lang))


@router.message(ProfileEdit.description)
async def save_desc(message: Message, state: FSMContext, session: AsyncSession, user: User):
    creator = await _get_creator(session, user)
    if creator:
        creator.experience = (message.text or "").strip()
        await session.commit()
    await state.clear()
    await message.answer(t("profile_saved", user.lang))
    await message.answer(_profile_text(creator, user.lang), reply_markup=_profile_keyboard(user.lang))


# --- Мои работы (CRUD) ---------------------------------------------------


def _works_keyboard(works, lang) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=w.title, callback_data=f"prof:work:{w.id}")] for w in works]
    rows.append([InlineKeyboardButton(text=t("back", lang), callback_data="prof:root")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _work_keyboard(work_id: int, lang) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=t("btn_price_rent", lang), callback_data=f"prof:price:rent:{work_id}"),
                InlineKeyboardButton(text=t("btn_price_buy", lang), callback_data=f"prof:price:buy:{work_id}"),
            ],
            [InlineKeyboardButton(text=t("btn_delete_work", lang), callback_data=f"prof:del:{work_id}")],
            [InlineKeyboardButton(text=t("back", lang), callback_data="prof:works")],
        ]
    )


def _work_text(work, lang) -> str:
    return t(
        "work_detail", lang,
        title=work.title, genre=work.genre or "—", key=work.key or "—", bpm=work.bpm or "—",
        rent=_money(work.price_rent), buy=_money(work.price_buy),
        status=_status_text(work.moderation_status, lang),
    )


@router.callback_query(F.data == "prof:works")
async def my_works(call: CallbackQuery, session: AsyncSession, user: User):
    creator = await _get_creator(session, user)
    if creator is None:
        await call.answer()
        return
    works = await repo.list_creator_works(session, creator.id)
    if not works:
        await call.message.edit_text(t("works_empty", user.lang), reply_markup=_profile_keyboard(user.lang))
        await call.answer()
        return
    await call.message.edit_text(t("works_list_title", user.lang), reply_markup=_works_keyboard(works, user.lang))
    await call.answer()


@router.callback_query(F.data.startswith("prof:work:"))
async def open_work(call: CallbackQuery, session: AsyncSession, user: User):
    work_id = int(call.data.split(":")[2])
    creator = await _get_creator(session, user)
    work = await repo.get_creator_work(session, work_id, creator.id) if creator else None
    if work is None:
        await call.answer()
        return
    await call.message.edit_text(_work_text(work, user.lang), reply_markup=_work_keyboard(work.id, user.lang))
    if work.cover_file_id:
        await call.message.answer_photo(work.cover_file_id)
    if work.audio_file_id:
        await call.message.answer_audio(work.audio_file_id, title=work.title)
    await call.answer()


@router.callback_query(F.data.startswith("prof:del:"))
async def delete_work(call: CallbackQuery, session: AsyncSession, user: User):
    work_id = int(call.data.split(":")[2])
    creator = await _get_creator(session, user)
    work = await repo.get_creator_work(session, work_id, creator.id) if creator else None
    if work is None:
        await call.answer()
        return
    await session.delete(work)
    await session.commit()
    works = await repo.list_creator_works(session, creator.id)
    await call.answer(t("work_deleted", user.lang), show_alert=True)
    if works:
        await call.message.edit_text(t("works_list_title", user.lang), reply_markup=_works_keyboard(works, user.lang))
    else:
        await call.message.edit_text(t("works_empty", user.lang), reply_markup=_profile_keyboard(user.lang))


@router.callback_query(F.data.startswith("prof:price:"))
async def ask_price(call: CallbackQuery, state: FSMContext, session: AsyncSession, user: User):
    _, _, kind, work_id_raw = call.data.split(":")
    creator = await _get_creator(session, user)
    work = await repo.get_creator_work(session, int(work_id_raw), creator.id) if creator else None
    if work is None:
        await call.answer()
        return
    await state.set_state(ProfileEdit.price)
    await state.update_data(work_id=work.id, price_kind=kind)
    await call.message.answer(t("work_ask_price", user.lang))
    await call.answer()


@router.message(ProfileEdit.price)
async def save_price(message: Message, state: FSMContext, session: AsyncSession, user: User):
    raw = (message.text or "").strip().replace(",", ".").replace(" ", "")
    try:
        price = Decimal(raw)
    except InvalidOperation:
        await message.answer(t("work_price_invalid", user.lang))
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
    await message.answer(t("work_price_updated", user.lang))
    await message.answer(_work_text(work, user.lang), reply_markup=_work_keyboard(work.id, user.lang))
