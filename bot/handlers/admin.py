from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    InputMediaVideo,
    Message,
)
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import Creator, CreatorStatus, Lang, ModerationStatus, Order, User, Work
from bot.db.repositories import works as repo
from bot.filters import IsAdmin
from bot.handlers.beats import parse_bpm
from bot.locales import t
from bot.services.forms import cancel_kb, read_text
from bot.services.media import detect_audio
from bot.services.moderation import creator_card, send_work_card
from bot.services.money import fmt_money as _money
from bot.services.money import parse_money
from bot.services.order_view import contact as _contact
from bot.services.text import EXPERIENCE_MAX, GENRE_MAX, KEY_MAX, SERVICE_MAX, SOCIALS_MAX, TITLE_MAX, esc
from bot.services.ui import replace_card
from bot.states.admin import AdminStates

router = Router()
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())

L = Lang.ru  # админ-панель всегда на русском

# Исполнителей на странице: длинный список целиком упирается в лимиты Telegram.
CREATORS_PAGE = 20


# =========================================================================
# КОРЕНЬ
# =========================================================================


def _root_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t("adm_btn_queue", L), callback_data="adm:queue")],
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
# ОЧЕРЕДЬ МОДЕРАЦИИ
# =========================================================================


@router.callback_query(F.data == "adm:queue")
async def adm_queue(call: CallbackQuery, session: AsyncSession):
    """Всё, что ждёт решения: раньше пропущенную карточку в личке было не найти."""
    creators = await repo.list_pending_creators(session)
    works = await repo.list_pending_works(session)
    rows = [
        [InlineKeyboardButton(
            text=f"👤 {u.nickname or u.username or c.id} · {c.service or '—'}"[:60],
            callback_data=f"adm:qc:{c.id}",
        )]
        for c, u in creators
    ] + [
        [InlineKeyboardButton(text=f"🎵 {w.title} · #{w.id}"[:60], callback_data=f"adm:qw:{w.id}")]
        for w in works
    ]
    rows.append([InlineKeyboardButton(text=t("back", L), callback_data="adm:root")])
    text = t("adm_queue_title", L, creators=len(creators), works=len(works)) if (creators or works) \
        else t("adm_queue_empty", L)
    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await call.answer()


@router.callback_query(F.data.startswith("adm:qc:"))
async def adm_queue_creator(call: CallbackQuery, session: AsyncSession):
    pair = await repo.get_creator_full(session, int(call.data.split(":")[2]))
    if pair is None or pair[0].status != CreatorStatus.pending:
        await call.answer(t("adm_queue_done", L), show_alert=True)
        return
    creator, user = pair
    text, kb = creator_card(user, creator)
    await call.message.answer(text, reply_markup=kb)
    await call.answer()


@router.callback_query(F.data.startswith("adm:qw:"))
async def adm_queue_work(call: CallbackQuery, session: AsyncSession, bot: Bot):
    pair = await repo.get_work_with_author(session, int(call.data.split(":")[2]))
    if pair is None or pair[0].moderation_status != ModerationStatus.pending:
        await call.answer(t("adm_queue_done", L), show_alert=True)
        return
    work, author = pair
    await send_work_card(bot, work, author, await repo.work_catalog_type(session, work))
    await call.answer()


# =========================================================================
# ИСПОЛНИТЕЛИ
# =========================================================================


def _cstatus(status: CreatorStatus) -> str:
    return t(f"cstatus_{status.value}", L)


async def _show_creators(call: CallbackQuery, session: AsyncSession, page: int = 0):
    total = await repo.count_creators(session)
    if not total:
        await call.message.edit_text(t("adm_creators_empty", L), reply_markup=_root_keyboard())
        return
    pages = (total + CREATORS_PAGE - 1) // CREATORS_PAGE
    page = max(0, min(page, pages - 1))
    creators = await repo.list_creators(session, offset=page * CREATORS_PAGE, limit=CREATORS_PAGE)
    rows = [
        [InlineKeyboardButton(
            text=f"{_cstatus(c.status)[:2]} {u.nickname or u.username or c.id} · {_money(c.balance)}₽",
            callback_data=f"adm:creator:{c.id}",
        )]
        for c, u in creators
    ]
    if pages > 1:
        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"adm:creators:{page - 1}"))
        nav.append(InlineKeyboardButton(text=f"{page + 1}/{pages}", callback_data=f"adm:creators:{page}"))
        if page < pages - 1:
            nav.append(InlineKeyboardButton(text="➡️", callback_data=f"adm:creators:{page + 1}"))
        rows.append(nav)
    rows.append([InlineKeyboardButton(text=t("back", L), callback_data="adm:root")])
    await call.message.edit_text(t("adm_creators_title", L), reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@router.callback_query(F.data == "adm:creators")
async def adm_creators(call: CallbackQuery, session: AsyncSession):
    await _show_creators(call, session)
    await call.answer()


@router.callback_query(F.data.startswith("adm:creators:"))
async def adm_creators_page(call: CallbackQuery, session: AsyncSession):
    try:
        await _show_creators(call, session, int(call.data.split(":")[2]))
    except Exception:
        pass  # «message is not modified» при нажатии на номер текущей страницы
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
            [InlineKeyboardButton(text=t("btn_view_portfolio", L), callback_data=f"pfopen:{creator.id}")],
            [toggle],
            [InlineKeyboardButton(text=t("adm_btn_del_creator", L), callback_data=f"adm:cdelete:{creator.id}")],
            [InlineKeyboardButton(text=t("back", L), callback_data="adm:creators")],
        ]
    )


def _creator_card_text(creator: Creator, user: User) -> str:
    return t(
        "adm_creator_card", L,
        cid=creator.id, contact=_contact(user), nickname=esc(user.nickname),
        service=esc(creator.service), status=_cstatus(creator.status),
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
async def adm_delete_creator_ask(call: CallbackQuery, session: AsyncSession):
    """Удаление необратимо (работы и портфолио уходят каскадом) — сначала подтверждение."""
    cid = int(call.data.split(":")[2])
    pair = await repo.get_creator_full(session, cid)
    if pair is None:
        await call.answer()
        return
    creator, user = pair
    works = await session.scalar(select(func.count(Work.id)).where(Work.creator_id == cid))
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("adm_btn_confirm_delete", L), callback_data=f"adm:cdelok:{cid}")],
        [InlineKeyboardButton(text=t("back", L), callback_data=f"adm:creator:{cid}")],
    ])
    await call.message.edit_text(
        t("adm_confirm_del_creator", L, contact=_contact(user), works=works or 0), reply_markup=kb,
    )
    await call.answer()


@router.callback_query(F.data.startswith("adm:cdelok:"))
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
    await call.message.answer(t("adm_ask_credit" if op == "add" else "adm_ask_writeoff", L), reply_markup=cancel_kb(L))
    await call.answer()


@router.message(AdminStates.writeoff)
async def adm_balance_save(message: Message, state: FSMContext, session: AsyncSession):
    # направление задаёт кнопка (начислить/списать), поэтому сумма всегда положительная
    amount = parse_money(message.text)
    if amount is None:
        await message.answer(t("adm_writeoff_invalid", L), reply_markup=cancel_kb(L))
        return
    data = await state.get_data()
    op = data.get("op", "sub")
    await state.clear()
    pair = await repo.get_creator_full(session, data["creator_id"])
    if pair:
        creator = pair[0]
        creator.balance = (creator.balance or 0) + (amount if op == "add" else -amount)
        await session.commit()
        done_key = "adm_credit_done" if op == "add" else "adm_writeoff_done"
        await message.answer(t(done_key, L, amount=_money(amount), balance=_money(creator.balance)))


# --- Ручное добавление исполнителя --------------------------------------


@router.callback_query(F.data == "adm:addcreator")
async def adm_add_creator_ask(call: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.add_creator)
    await call.message.answer(t("adm_ask_add_creator", L), reply_markup=cancel_kb(L))
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
# те же лимиты, что у исполнителя: карточки и профиль должны влезать в сообщение
_EF_MAX = {"service": SERVICE_MAX, "socials": SOCIALS_MAX, "experience": EXPERIENCE_MAX}


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
    await call.message.answer(t(prompt, L), reply_markup=cancel_kb(L))
    await call.answer()


@router.message(AdminStates.creator_field)
async def adm_creator_edit_save(message: Message, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    value = await read_text(message, L, _EF_MAX[data["field"]])
    if value is None:
        return
    await state.clear()
    creator = await session.get(Creator, data["creator_id"])
    if creator is None:
        return
    setattr(creator, data["field"], value)
    await session.commit()
    await message.answer(t("adm_profile_saved", L))


# --- Загрузка работы за автора -------------------------------------------


@router.callback_query(F.data.startswith("adm:cwork:"))
async def adm_creator_add_work(call: CallbackQuery):
    cid = int(call.data.split(":")[2])
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t("addwork_beat", L), callback_data=f"adm:cworkbeat:{cid}"),
        InlineKeyboardButton(text=t("addwork_visual", L), callback_data=f"adm:cworkvisual:{cid}"),
        InlineKeyboardButton(text=t("addwork_video", L), callback_data=f"adm:cworkvideo:{cid}"),
    ]])
    await call.message.answer(t("addwork_choose", L), reply_markup=kb)
    await call.answer()


@router.callback_query(F.data.startswith("adm:cworkbeat:"))
async def adm_creator_add_beat(call: CallbackQuery, state: FSMContext):
    from bot.handlers.beats import _BEAT_STEPS
    from bot.services.forms import step
    from bot.states.beats import AddBeat

    cid = int(call.data.split(":")[2])
    await state.clear()
    await state.set_state(AddBeat.title)
    await state.update_data(target_creator_id=cid)
    await call.message.answer(step(1, _BEAT_STEPS, "addbeat_title", L), reply_markup=cancel_kb(L))
    await call.answer()


@router.callback_query(F.data.startswith("adm:cworkvisual:"))
async def adm_creator_add_visual(call: CallbackQuery, state: FSMContext):
    from bot.handlers.beats import _VISUAL_STEPS
    from bot.services.forms import step
    from bot.states.beats import AddVisual

    cid = int(call.data.split(":")[2])
    await state.clear()
    await state.set_state(AddVisual.title)
    await state.update_data(target_creator_id=cid)
    await call.message.answer(step(1, _VISUAL_STEPS, "addvisual_title", L), reply_markup=cancel_kb(L))
    await call.answer()


@router.callback_query(F.data.startswith("adm:cworkvideo:"))
async def adm_creator_add_video(call: CallbackQuery, state: FSMContext):
    from bot.handlers.beats import _VIDEO_STEPS
    from bot.services.forms import step
    from bot.states.beats import AddVideo

    cid = int(call.data.split(":")[2])
    await state.clear()
    await state.set_state(AddVideo.title)
    await state.update_data(target_creator_id=cid)
    await call.message.answer(step(1, _VIDEO_STEPS, "addvideo_title", L), reply_markup=cancel_kb(L))
    await call.answer()


# =========================================================================
# КАТАЛОГ РАБОТ
# =========================================================================


async def _show_works(call: CallbackQuery, session: AsyncSession):
    works = await repo.list_recent_works(session)
    if not works:
        await replace_card(call, t("adm_works_empty", L), _root_keyboard())
        return
    rows = [
        [InlineKeyboardButton(text=f"{w.title} · #{w.id}", callback_data=f"adm:work:{w.id}")]
        for w in works
    ]
    rows.append([InlineKeyboardButton(text=t("back", L), callback_data="adm:root")])
    await replace_card(call, t("adm_works_title", L), InlineKeyboardMarkup(inline_keyboard=rows))


@router.callback_query(F.data == "adm:works")
async def adm_works(call: CallbackQuery, session: AsyncSession):
    await _show_works(call, session)
    await call.answer()


def _work_keyboard(work_id: int, has_audio: bool = False, ctype: str = "beat") -> InlineKeyboardMarkup:
    rows = [[
        InlineKeyboardButton(text=t("adm_btn_edit_title", L), callback_data=f"adm:wf:title:{work_id}"),
        InlineKeyboardButton(
            text=t("adm_btn_edit_video" if ctype == "video" else "adm_btn_edit_cover", L),
            callback_data=f"adm:wcover:{work_id}",
        ),
    ]]
    if ctype in ("visual", "video"):
        # у визуала/видео нет аренды/тональности/BPM/аудио — только тип и цена выкупа
        rows.append([
            InlineKeyboardButton(text=t("adm_btn_edit_type", L), callback_data=f"adm:wf:genre:{work_id}"),
            InlineKeyboardButton(text=t("adm_btn_edit_buy", L), callback_data=f"adm:wf:price_buy:{work_id}"),
        ])
    else:
        rows += [
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
        ]
        if has_audio:
            rows.append([InlineKeyboardButton(text=t("beat_listen", L), callback_data=f"beat:listen:{work_id}")])
    rows.append([InlineKeyboardButton(text=t("adm_btn_del_work", L), callback_data=f"adm:wdel:{work_id}")])
    rows.append([InlineKeyboardButton(text=t("back", L), callback_data="adm:works")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _work_card_content(work, author, ctype: str = "beat") -> tuple[str | None, str, InlineKeyboardMarkup]:
    if ctype in ("visual", "video"):
        text = t(
            "adm_work_card_video" if ctype == "video" else "adm_work_card_visual", L,
            title=esc(work.title), wid=work.id, author=_contact(author),
            vtype=esc(work.genre), buy=_money(work.price_buy),
            status=t(f"status_{work.moderation_status.value}", L),
        )
    else:
        text = t(
            "adm_work_card", L,
            title=esc(work.title), wid=work.id, author=_contact(author),
            genre=esc(work.genre), key=esc(work.key), bpm=work.bpm or "—",
            rent=_money(work.price_rent), buy=_money(work.price_buy),
            status=t(f"status_{work.moderation_status.value}", L),
        )
    return work.cover_file_id, text, _work_keyboard(work.id, bool(work.audio_file_id), ctype)


async def _show_work_card(call: CallbackQuery, session: AsyncSession, work_id: int):
    pair = await repo.get_work_with_author(session, work_id)
    if pair is None:
        await call.answer()
        return
    ctype = await repo.work_catalog_type(session, pair[0])
    cover, text, kb = _work_card_content(*pair, ctype)
    if ctype == "video":
        await replace_card(call, text, kb, video=cover)
    else:
        await replace_card(call, text, kb, photo=cover)


async def _refresh_work_card(bot: Bot, session: AsyncSession, data: dict, media_changed: bool = False):
    """Обновляет карточку работы на месте после правки (подпись или само медиа)."""
    if not data.get("card_msg"):
        return
    pair = await repo.get_work_with_author(session, data["work_id"])
    if pair is None:
        return
    ctype = await repo.work_catalog_type(session, pair[0])
    cover, text, kb = _work_card_content(*pair, ctype)
    try:
        if media_changed and cover:
            media_cls = InputMediaVideo if ctype == "video" else InputMediaPhoto
            await bot.edit_message_media(
                media=media_cls(media=cover, caption=text),
                chat_id=data["card_chat"], message_id=data["card_msg"], reply_markup=kb,
            )
        else:
            await bot.edit_message_caption(
                chat_id=data["card_chat"], message_id=data["card_msg"], caption=text, reply_markup=kb
            )
    except Exception:
        pass


@router.callback_query(F.data.startswith("adm:work:"))
async def adm_work_card(call: CallbackQuery, session: AsyncSession):
    await _show_work_card(call, session, int(call.data.split(":")[2]))
    await call.answer()


@router.callback_query(F.data.startswith("adm:wdel:"))
async def adm_work_delete_ask(call: CallbackQuery):
    """Подтверждение удаления прямо на карточке работы."""
    work_id = int(call.data.split(":")[2])
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("adm_btn_confirm_delete", L), callback_data=f"adm:wdelok:{work_id}")],
        [InlineKeyboardButton(text=t("back", L), callback_data=f"adm:work:{work_id}")],
    ])
    try:
        await call.message.edit_reply_markup(reply_markup=kb)
    except Exception:
        pass
    await call.answer(t("adm_confirm_del_work", L))


@router.callback_query(F.data.startswith("adm:wdelok:"))
async def adm_work_delete(call: CallbackQuery, session: AsyncSession):
    work = await repo.get_work(session, int(call.data.split(":")[2]))
    if work:
        await session.delete(work)
        await session.commit()
    await call.answer(t("adm_work_deleted", L), show_alert=True)
    await _show_works(call, session)


_NUMERIC_FIELDS = {"price_rent", "price_buy", "bpm"}
# длины колонок works.* — длиннее БД не примет
_TEXT_FIELD_MAX = {"title": TITLE_MAX, "genre": GENRE_MAX, "key": KEY_MAX}


@router.callback_query(F.data.startswith("adm:wf:"))
async def adm_work_field_ask(call: CallbackQuery, state: FSMContext):
    _, _, field, work_id_raw = call.data.split(":")
    await state.set_state(AdminStates.work_value)
    await state.update_data(
        work_id=int(work_id_raw), field=field,
        card_chat=call.message.chat.id, card_msg=call.message.message_id,
    )
    if field == "bpm":
        prompt = t("adm_ask_bpm", L)
    elif field in ("price_rent", "price_buy"):
        prompt = t("adm_ask_price", L)
    elif field == "title":
        prompt = t("adm_ask_title", L)
    else:
        prompt = t("adm_ask_value", L)
    await call.message.answer(prompt, reply_markup=cancel_kb(L))
    await call.answer()


@router.message(AdminStates.work_value)
async def adm_work_field_save(message: Message, state: FSMContext, session: AsyncSession, bot: Bot):
    data = await state.get_data()
    field = data["field"]

    value: object
    if field == "bpm":
        value = parse_bpm(message.text)
    elif field in _NUMERIC_FIELDS:
        value = parse_money(message.text, allow_zero=True)
    else:
        value = await read_text(message, L, _TEXT_FIELD_MAX.get(field, GENRE_MAX))
        if value is None:
            return
    if value is None:
        await message.answer(t("adm_value_invalid", L), reply_markup=cancel_kb(L))
        return

    await state.clear()
    work = await repo.get_work(session, data["work_id"])
    if work is None:
        return
    setattr(work, field, value)
    await session.commit()
    await _refresh_work_card(bot, session, data)
    await message.answer(t("adm_work_updated", L))


@router.callback_query(F.data.startswith("adm:waudio:"))
async def adm_work_audio_ask(call: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.work_audio)
    await state.update_data(
        work_id=int(call.data.split(":")[2]),
        card_chat=call.message.chat.id, card_msg=call.message.message_id,
    )
    await call.message.answer(t("adm_ask_audio", L), reply_markup=cancel_kb(L))
    await call.answer()


@router.message(AdminStates.work_audio)
async def adm_work_audio_save(message: Message, state: FSMContext, session: AsyncSession, bot: Bot):
    found = detect_audio(message)
    if found is None:
        await message.answer(t("addbeat_audio_invalid", L), reply_markup=cancel_kb(L))
        return
    kind, file_id = found
    data = await state.get_data()
    await state.clear()
    work = await repo.get_work(session, data["work_id"])
    if work:
        work.audio_file_id, work.audio_kind = file_id, kind
        await session.commit()
    await _refresh_work_card(bot, session, data)
    await message.answer(t("adm_work_updated", L))


@router.callback_query(F.data.startswith("adm:wcover:"))
async def adm_work_cover_ask(call: CallbackQuery, state: FSMContext, session: AsyncSession):
    work = await repo.get_work(session, int(call.data.split(":")[2]))
    if work is None:
        await call.answer()
        return
    ctype = await repo.work_catalog_type(session, work)
    await state.set_state(AdminStates.work_cover)
    await state.update_data(
        work_id=work.id, ctype=ctype,
        card_chat=call.message.chat.id, card_msg=call.message.message_id,
    )
    await call.message.answer(t("adm_ask_video" if ctype == "video" else "adm_ask_cover", L), reply_markup=cancel_kb(L))
    await call.answer()


@router.message(AdminStates.work_cover)
async def adm_work_cover_save(message: Message, state: FSMContext, session: AsyncSession, bot: Bot):
    data = await state.get_data()
    if data.get("ctype") == "video":
        file_id = message.video.file_id if message.video else None
        invalid_key = "addvideo_file_invalid"
    else:
        file_id = message.photo[-1].file_id if message.photo else None
        invalid_key = "addvisual_cover_invalid"
    if file_id is None:
        await message.answer(t(invalid_key, L), reply_markup=cancel_kb(L))
        return
    await state.clear()
    work = await repo.get_work(session, data["work_id"])
    if work:
        work.cover_file_id = file_id
        await session.commit()
    await _refresh_work_card(bot, session, data, media_changed=True)
    await message.answer(t("adm_work_updated", L))
