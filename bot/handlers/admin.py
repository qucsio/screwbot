from decimal import Decimal, InvalidOperation

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import Creator, CreatorStatus, Lang, Order, User
from bot.db.repositories import works as repo
from bot.filters import IsAdmin
from bot.locales import t
from bot.states.admin import AdminStates

router = Router()
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())

L = Lang.ru  # админ-панель всегда на русском


def _money(v) -> str:
    return f"{v:g}" if v is not None else "—"


def _contact(user: User) -> str:
    if user.username:
        return f"@{user.username}"
    return f'<a href="tg://user?id={user.tg_id}">{user.nickname or "профиль"}</a>'


# =========================================================================
# КОРЕНЬ
# =========================================================================


def _root_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t("adm_btn_creators", L), callback_data="adm:creators")],
            [InlineKeyboardButton(text=t("adm_btn_works", L), callback_data="adm:works")],
            [InlineKeyboardButton(text=t("adm_btn_add_creator", L), callback_data="adm:addcreator")],
        ]
    )


@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(t("admin_root", L), reply_markup=_root_keyboard())


@router.callback_query(F.data == "adm:root")
async def adm_root(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text(t("admin_root", L), reply_markup=_root_keyboard())
    await call.answer()


# =========================================================================
# ИСПОЛНИТЕЛИ
# =========================================================================


def _cstatus(status: CreatorStatus) -> str:
    return t(f"cstatus_{status.value}", L)


async def _show_creators(call: CallbackQuery, session: AsyncSession):
    creators = await repo.list_creators(session)
    if not creators:
        await call.message.edit_text(t("adm_creators_empty", L), reply_markup=_root_keyboard())
        return
    rows = [
        [InlineKeyboardButton(
            text=f"{_cstatus(c.status)[:2]} {u.nickname or u.username or c.id} · {_money(c.balance)}₽",
            callback_data=f"adm:creator:{c.id}",
        )]
        for c, u in creators
    ]
    rows.append([InlineKeyboardButton(text=t("back", L), callback_data="adm:root")])
    await call.message.edit_text(t("adm_creators_title", L), reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@router.callback_query(F.data == "adm:creators")
async def adm_creators(call: CallbackQuery, session: AsyncSession):
    await _show_creators(call, session)
    await call.answer()


def _creator_keyboard(creator: Creator) -> InlineKeyboardMarkup:
    toggle = (
        InlineKeyboardButton(text=t("adm_btn_unblock", L), callback_data=f"adm:cunblock:{creator.id}")
        if creator.status == CreatorStatus.blocked
        else InlineKeyboardButton(text=t("adm_btn_block", L), callback_data=f"adm:cblock:{creator.id}")
    )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=t("adm_btn_credit", L), callback_data=f"adm:bal:add:{creator.id}"),
                InlineKeyboardButton(text=t("adm_btn_writeoff", L), callback_data=f"adm:bal:sub:{creator.id}"),
            ],
            [
                InlineKeyboardButton(text=t("adm_btn_edit_profile", L), callback_data=f"adm:cprofile:{creator.id}"),
                InlineKeyboardButton(text=t("adm_btn_add_work", L), callback_data=f"adm:cwork:{creator.id}"),
            ],
            [toggle],
            [InlineKeyboardButton(text=t("adm_btn_del_creator", L), callback_data=f"adm:cdelete:{creator.id}")],
            [InlineKeyboardButton(text=t("back", L), callback_data="adm:creators")],
        ]
    )


def _creator_card_text(creator: Creator, user: User) -> str:
    return t(
        "adm_creator_card", L,
        cid=creator.id, contact=_contact(user), nickname=user.nickname or "—",
        service=creator.service or "—", status=_cstatus(creator.status),
        balance=_money(creator.balance),
    )


async def _show_creator_card(call: CallbackQuery, session: AsyncSession, creator_id: int):
    pair = await repo.get_creator_full(session, creator_id)
    if pair is None:
        await call.answer()
        return
    creator, user = pair
    await call.message.edit_text(_creator_card_text(creator, user), reply_markup=_creator_keyboard(creator))


@router.callback_query(F.data.startswith("adm:creator:"))
async def adm_creator_card(call: CallbackQuery, session: AsyncSession):
    await _show_creator_card(call, session, int(call.data.split(":")[2]))
    await call.answer()


@router.callback_query(F.data.startswith("modauthor:"))
async def adm_open_author(call: CallbackQuery, session: AsyncSession):
    """Открыть карточку исполнителя из карточки модерации (новым сообщением)."""
    cid = int(call.data.split(":")[1])
    pair = await repo.get_creator_full(session, cid)
    if pair is None:
        await call.answer("not found", show_alert=True)
        return
    creator, user = pair
    await call.message.answer(_creator_card_text(creator, user), reply_markup=_creator_keyboard(creator))
    await call.answer()


@router.callback_query(F.data.startswith("adm:cblock:"))
async def adm_block(call: CallbackQuery, session: AsyncSession):
    cid = int(call.data.split(":")[2])
    pair = await repo.get_creator_full(session, cid)
    if pair:
        pair[0].status = CreatorStatus.blocked
        await session.commit()
        await _show_creator_card(call, session, cid)
    await call.answer(t("adm_creator_blocked", L), show_alert=True)


@router.callback_query(F.data.startswith("adm:cunblock:"))
async def adm_unblock(call: CallbackQuery, session: AsyncSession):
    cid = int(call.data.split(":")[2])
    pair = await repo.get_creator_full(session, cid)
    if pair:
        pair[0].status = CreatorStatus.approved
        await session.commit()
        await _show_creator_card(call, session, cid)
    await call.answer(t("adm_creator_unblocked", L))


@router.callback_query(F.data.startswith("adm:cdelete:"))
async def adm_delete_creator(call: CallbackQuery, session: AsyncSession):
    cid = int(call.data.split(":")[2])
    pair = await repo.get_creator_full(session, cid)
    if pair:
        # отвязываем от заказов (FK без ON DELETE), работы уйдут каскадом
        await session.execute(
            update(Order).where(Order.creator_id == cid).values(creator_id=None)
        )
        await session.delete(pair[0])
        await session.commit()
    await call.answer(t("adm_creator_deleted", L), show_alert=True)
    await _show_creators(call, session)


@router.callback_query(F.data.startswith("adm:bal:"))
async def adm_balance_ask(call: CallbackQuery, state: FSMContext):
    _, _, op, cid_raw = call.data.split(":")   # op: add | sub
    await state.set_state(AdminStates.writeoff)
    await state.update_data(creator_id=int(cid_raw), op=op)
    await call.message.answer(t("adm_ask_credit" if op == "add" else "adm_ask_writeoff", L))
    await call.answer()


@router.message(AdminStates.writeoff)
async def adm_balance_save(message: Message, state: FSMContext, session: AsyncSession):
    raw = (message.text or "").strip().replace(",", ".").replace(" ", "")
    try:
        amount = Decimal(raw)
    except InvalidOperation:
        await message.answer(t("adm_writeoff_invalid", L))
        return
    data = await state.get_data()
    op = data.get("op", "sub")
    await state.clear()
    pair = await repo.get_creator_full(session, data["creator_id"])
    if pair:
        creator = pair[0]
        creator.balance = (creator.balance or Decimal(0)) + (amount if op == "add" else -amount)
        await session.commit()
        done_key = "adm_credit_done" if op == "add" else "adm_writeoff_done"
        await message.answer(t(done_key, L, amount=amount, balance=_money(creator.balance)))


# --- Ручное добавление исполнителя --------------------------------------


@router.callback_query(F.data == "adm:addcreator")
async def adm_add_creator_ask(call: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.add_creator)
    await call.message.answer(t("adm_ask_add_creator", L))
    await call.answer()


@router.message(AdminStates.add_creator)
async def adm_add_creator_save(message: Message, state: FSMContext, session: AsyncSession):
    await state.clear()
    user = await repo.find_user_by_query(session, message.text or "")
    if user is None:
        await message.answer(t("adm_user_not_found", L))
        return
    res = await session.execute(select(Creator).where(Creator.user_id == user.id))
    creator = res.scalar_one_or_none()
    if creator is None:
        creator = Creator(user_id=user.id, status=CreatorStatus.approved, service="—")
        session.add(creator)
    else:
        creator.status = CreatorStatus.approved
    await session.commit()
    await message.answer(t("adm_creator_added", L, contact=_contact(user)))


# --- Правка профиля исполнителя админом ----------------------------------

_EF_FIELDS = {"service": "service", "socials": "socials", "desc": "experience"}


@router.callback_query(F.data.startswith("adm:cprofile:"))
async def adm_creator_profile(call: CallbackQuery):
    cid = int(call.data.split(":")[2])
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=t("adm_btn_ef_service", L), callback_data=f"adm:cef:service:{cid}"),
            InlineKeyboardButton(text=t("adm_btn_ef_socials", L), callback_data=f"adm:cef:socials:{cid}"),
            InlineKeyboardButton(text=t("adm_btn_ef_desc", L), callback_data=f"adm:cef:desc:{cid}"),
        ],
        [InlineKeyboardButton(text=t("back", L), callback_data=f"adm:creator:{cid}")],
    ])
    await call.message.edit_text(t("adm_cprofile_title", L, cid=cid), reply_markup=kb)
    await call.answer()


@router.callback_query(F.data.startswith("adm:cef:"))
async def adm_creator_edit_ask(call: CallbackQuery, state: FSMContext):
    _, _, field, cid_raw = call.data.split(":")
    await state.set_state(AdminStates.creator_field)
    await state.update_data(creator_id=int(cid_raw), field=_EF_FIELDS[field])
    prompt = {"service": "adm_ask_service", "socials": "adm_ask_socials", "desc": "adm_ask_desc"}[field]
    await call.message.answer(t(prompt, L))
    await call.answer()


@router.message(AdminStates.creator_field)
async def adm_creator_edit_save(message: Message, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    await state.clear()
    creator = await session.get(Creator, data["creator_id"])
    if creator is None:
        return
    setattr(creator, data["field"], (message.text or "").strip())
    await session.commit()
    await message.answer(t("adm_profile_saved", L))


# --- Загрузка работы за автора -------------------------------------------


@router.callback_query(F.data.startswith("adm:cwork:"))
async def adm_creator_add_work(call: CallbackQuery):
    cid = int(call.data.split(":")[2])
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t("addwork_beat", L), callback_data=f"adm:cworkbeat:{cid}"),
        InlineKeyboardButton(text=t("addwork_visual", L), callback_data=f"adm:cworkvisual:{cid}"),
    ]])
    await call.message.answer(t("addwork_choose", L), reply_markup=kb)
    await call.answer()


@router.callback_query(F.data.startswith("adm:cworkbeat:"))
async def adm_creator_add_beat(call: CallbackQuery, state: FSMContext):
    from bot.states.beats import AddBeat

    cid = int(call.data.split(":")[2])
    await state.clear()
    await state.set_state(AddBeat.title)
    await state.update_data(target_creator_id=cid)
    await call.message.answer(t("addbeat_title", L))
    await call.answer()


@router.callback_query(F.data.startswith("adm:cworkvisual:"))
async def adm_creator_add_visual(call: CallbackQuery, state: FSMContext):
    from bot.states.beats import AddVisual

    cid = int(call.data.split(":")[2])
    await state.clear()
    await state.set_state(AddVisual.title)
    await state.update_data(target_creator_id=cid)
    await call.message.answer(t("addvisual_title", L))
    await call.answer()


# =========================================================================
# КАТАЛОГ РАБОТ
# =========================================================================


async def _show_works(call: CallbackQuery, session: AsyncSession):
    works = await repo.list_recent_works(session)
    if not works:
        await call.message.edit_text(t("adm_works_empty", L), reply_markup=_root_keyboard())
        return
    rows = [
        [InlineKeyboardButton(text=f"{w.title} · #{w.id}", callback_data=f"adm:work:{w.id}")]
        for w in works
    ]
    rows.append([InlineKeyboardButton(text=t("back", L), callback_data="adm:root")])
    await call.message.edit_text(t("adm_works_title", L), reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@router.callback_query(F.data == "adm:works")
async def adm_works(call: CallbackQuery, session: AsyncSession):
    await _show_works(call, session)
    await call.answer()


def _work_keyboard(work_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=t("adm_btn_edit_rent", L), callback_data=f"adm:wf:price_rent:{work_id}"),
                InlineKeyboardButton(text=t("adm_btn_edit_buy", L), callback_data=f"adm:wf:price_buy:{work_id}"),
            ],
            [
                InlineKeyboardButton(text=t("adm_btn_edit_genre", L), callback_data=f"adm:wf:genre:{work_id}"),
                InlineKeyboardButton(text=t("adm_btn_edit_key", L), callback_data=f"adm:wf:key:{work_id}"),
                InlineKeyboardButton(text=t("adm_btn_edit_bpm", L), callback_data=f"adm:wf:bpm:{work_id}"),
            ],
            [InlineKeyboardButton(text=t("adm_btn_edit_audio", L), callback_data=f"adm:waudio:{work_id}")],
            [InlineKeyboardButton(text=t("adm_btn_del_work", L), callback_data=f"adm:wdel:{work_id}")],
            [InlineKeyboardButton(text=t("back", L), callback_data="adm:works")],
        ]
    )


async def _show_work_card(call: CallbackQuery, session: AsyncSession, work_id: int):
    pair = await repo.get_work_with_author(session, work_id)
    if pair is None:
        await call.answer()
        return
    work, author = pair
    text = t(
        "adm_work_card", L,
        title=work.title, wid=work.id, author=_contact(author),
        genre=work.genre or "—", key=work.key or "—", bpm=work.bpm or "—",
        rent=_money(work.price_rent), buy=_money(work.price_buy),
        status=t(f"status_{work.moderation_status.value}", L),
    )
    await call.message.edit_text(text, reply_markup=_work_keyboard(work.id))
    # прикладываем медиа отдельными сообщениями (обложка, для бита — аудио)
    if work.cover_file_id:
        await call.message.answer_photo(work.cover_file_id)
    if work.audio_file_id:
        await call.message.answer_audio(work.audio_file_id, title=work.title)


@router.callback_query(F.data.startswith("adm:work:"))
async def adm_work_card(call: CallbackQuery, session: AsyncSession):
    await _show_work_card(call, session, int(call.data.split(":")[2]))
    await call.answer()


@router.callback_query(F.data.startswith("adm:wdel:"))
async def adm_work_delete(call: CallbackQuery, session: AsyncSession):
    work = await repo.get_work(session, int(call.data.split(":")[2]))
    if work:
        await session.delete(work)
        await session.commit()
    await call.answer(t("adm_work_deleted", L), show_alert=True)
    await _show_works(call, session)


_NUMERIC_FIELDS = {"price_rent", "price_buy", "bpm"}


@router.callback_query(F.data.startswith("adm:wf:"))
async def adm_work_field_ask(call: CallbackQuery, state: FSMContext):
    _, _, field, work_id_raw = call.data.split(":")
    await state.set_state(AdminStates.work_value)
    await state.update_data(work_id=int(work_id_raw), field=field)
    if field == "bpm":
        prompt = t("adm_ask_bpm", L)
    elif field in ("price_rent", "price_buy"):
        prompt = t("adm_ask_price", L)
    else:
        prompt = t("adm_ask_value", L)
    await call.message.answer(prompt)
    await call.answer()


@router.message(AdminStates.work_value)
async def adm_work_field_save(message: Message, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    field = data["field"]
    raw = (message.text or "").strip()

    value: object
    if field in _NUMERIC_FIELDS:
        cleaned = raw.replace(",", ".").replace(" ", "")
        if field == "bpm":
            if not cleaned.isdigit():
                await message.answer(t("adm_value_invalid", L))
                return
            value = int(cleaned)
        else:
            try:
                value = Decimal(cleaned)
            except InvalidOperation:
                await message.answer(t("adm_value_invalid", L))
                return
    else:
        value = raw

    await state.clear()
    work = await repo.get_work(session, data["work_id"])
    if work is None:
        return
    setattr(work, field, value)
    await session.commit()
    await message.answer(t("adm_work_updated", L))


@router.callback_query(F.data.startswith("adm:waudio:"))
async def adm_work_audio_ask(call: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.work_audio)
    await state.update_data(work_id=int(call.data.split(":")[2]))
    await call.message.answer(t("adm_ask_audio", L))
    await call.answer()


@router.message(AdminStates.work_audio, F.audio | F.voice | F.document)
async def adm_work_audio_save(message: Message, state: FSMContext, session: AsyncSession):
    file = message.audio or message.voice or message.document
    data = await state.get_data()
    await state.clear()
    work = await repo.get_work(session, data["work_id"])
    if work:
        work.audio_file_id = file.file_id
        await session.commit()
    await message.answer(t("adm_work_updated", L))
