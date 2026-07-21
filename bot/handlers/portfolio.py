from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaAudio,
    InputMediaDocument,
    InputMediaPhoto,
    InputMediaVideo,
    Message,
)
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import Lang, MediaType, User
from bot.db.repositories import portfolio as repo
from bot.db.repositories.works import get_approved_creator
from bot.locales import t
from bot.services.forms import cancel_kb, guard_text
from bot.states.portfolio import AddPortfolio

router = Router()

_INPUT_MEDIA = {
    MediaType.photo: InputMediaPhoto,
    MediaType.video: InputMediaVideo,
    MediaType.audio: InputMediaAudio,
    MediaType.document: InputMediaDocument,
}


def detect_media(message: Message):
    """(MediaType, file_id) из сообщения или None, если это не медиа."""
    if message.photo:
        return MediaType.photo, message.photo[-1].file_id
    if message.video:
        return MediaType.video, message.video.file_id
    if message.audio or message.voice:
        return MediaType.audio, (message.audio or message.voice).file_id
    if message.document:
        return MediaType.document, message.document.file_id
    return None


def _caption(item, pos: int, total: int, lang: Lang) -> str:
    tail = f"\n{item.caption}" if item.caption else ""
    return t("portfolio_card", lang, pos=pos, total=total, caption=tail)


def _owner_keyboard(lang: Lang, item_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=t("beat_prev", lang), callback_data="portnav:prev"),
                InlineKeyboardButton(text=t("beat_next", lang), callback_data="portnav:next"),
            ],
            [InlineKeyboardButton(text=t("btn_portfolio_add", lang), callback_data="port:add")],
            [InlineKeyboardButton(text=t("btn_portfolio_del", lang), callback_data=f"port:del:{item_id}")],
        ]
    )


def _add_only_keyboard(lang: Lang) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=t("btn_portfolio_add", lang), callback_data="port:add")]]
    )


async def _send_card(target: Message, item, pos: int, total: int, lang: Lang, kb) -> None:
    caption = _caption(item, pos, total, lang)
    if item.media_type == MediaType.photo:
        await target.answer_photo(item.file_id, caption=caption, reply_markup=kb)
    elif item.media_type == MediaType.video:
        await target.answer_video(item.file_id, caption=caption, reply_markup=kb)
    elif item.media_type == MediaType.audio:
        await target.answer_audio(item.file_id, caption=caption, reply_markup=kb)
    else:
        await target.answer_document(item.file_id, caption=caption, reply_markup=kb)


async def _edit_or_resend(call: CallbackQuery, item, pos: int, total: int, lang: Lang, kb) -> None:
    media_cls = _INPUT_MEDIA[item.media_type]
    try:
        await call.message.edit_media(
            media_cls(media=item.file_id, caption=_caption(item, pos, total, lang)),
            reply_markup=kb,
        )
    except Exception:
        # Telegram может не дать заменить один тип медиа другим — пересобираем карточку.
        try:
            await call.message.delete()
        except Exception:
            pass
        await _send_card(call.message, item, pos, total, lang, kb)


# =========================================================================
# ПОРТФОЛИО ИСПОЛНИТЕЛЯ (панель, CRUD)
# =========================================================================


async def open_portfolio(message: Message, state: FSMContext, session: AsyncSession, user: User):
    creator = await get_approved_creator(session, user.id)
    if creator is None:
        await message.answer(t("portfolio_only_creator", user.lang))
        return
    items = await repo.list_items(session, creator.id)
    if not items:
        await message.answer(t("portfolio_empty", user.lang), reply_markup=_add_only_keyboard(user.lang))
        return
    await state.update_data(port_ids=[i.id for i in items], port_idx=0)
    await _send_card(message, items[0], 1, len(items), user.lang, _owner_keyboard(user.lang, items[0].id))


@router.callback_query(F.data.in_({"portnav:prev", "portnav:next"}))
async def portfolio_nav(call: CallbackQuery, state: FSMContext, session: AsyncSession, user: User):
    creator = await get_approved_creator(session, user.id)
    if creator is None:
        await call.answer()
        return
    data = await state.get_data()
    ids = data.get("port_ids") or []
    if not ids:
        await call.answer()
        return
    idx = (data.get("port_idx", 0) + (1 if call.data.endswith("next") else -1)) % len(ids)
    item = await repo.get_item(session, ids[idx], creator.id)
    if item is None:
        await call.answer()
        return
    await state.update_data(port_idx=idx)
    await _edit_or_resend(call, item, idx + 1, len(ids), user.lang, _owner_keyboard(user.lang, item.id))
    await call.answer()


@router.callback_query(F.data == "port:add")
async def portfolio_add(call: CallbackQuery, state: FSMContext, session: AsyncSession, user: User):
    creator = await get_approved_creator(session, user.id)
    if creator is None:
        await call.answer(t("portfolio_only_creator", user.lang), show_alert=True)
        return
    await state.set_state(AddPortfolio.media)
    await call.message.answer(t("portfolio_add_prompt", user.lang), reply_markup=cancel_kb(user.lang))
    await call.answer()


@router.message(AddPortfolio.media)
async def portfolio_receive_media(message: Message, state: FSMContext, user: User):
    found = detect_media(message)
    if found is None:
        await message.answer(t("need_media", user.lang), reply_markup=cancel_kb(user.lang))
        return
    media_type, file_id = found
    await state.update_data(pf_type=media_type.value, pf_file=file_id)
    await state.set_state(AddPortfolio.caption)
    await message.answer(t("portfolio_caption_prompt", user.lang), reply_markup=cancel_kb(user.lang))


@router.message(AddPortfolio.caption)
async def portfolio_save(message: Message, state: FSMContext, session: AsyncSession, user: User):
    text = guard_text(message)
    if text is None:
        await message.answer(t("need_text", user.lang), reply_markup=cancel_kb(user.lang))
        return
    caption = None if text == "-" else text
    data = await state.get_data()
    await state.clear()
    creator = await get_approved_creator(session, user.id)
    if creator is None:
        await message.answer(t("portfolio_only_creator", user.lang))
        return
    await repo.add_item(session, creator.id, MediaType(data["pf_type"]), data["pf_file"], caption)
    await message.answer(t("portfolio_saved", user.lang))
    await open_portfolio(message, state, session, user)


@router.callback_query(F.data.startswith("port:del:"))
async def portfolio_delete(call: CallbackQuery, state: FSMContext, session: AsyncSession, user: User):
    creator = await get_approved_creator(session, user.id)
    if creator is None:
        await call.answer()
        return
    item_id = int(call.data.split(":")[2])
    await repo.delete_item(session, item_id, creator.id)
    try:
        await call.message.delete()
    except Exception:
        pass
    await call.answer(t("portfolio_deleted", user.lang))
    await open_portfolio(call.message, state, session, user)


# =========================================================================
# ПРОСМОТР ПОРТФОЛИО АДМИНОМ (read-only, из карточки/заявки исполнителя)
# =========================================================================


def _admin_view_kb(creator_id: int, idx: int, total: int) -> InlineKeyboardMarkup:
    prev_idx = (idx - 1) % total
    next_idx = (idx + 1) % total
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text=t("beat_prev", Lang.ru), callback_data=f"pfv:{creator_id}:{prev_idx}"),
            InlineKeyboardButton(text=t("beat_next", Lang.ru), callback_data=f"pfv:{creator_id}:{next_idx}"),
        ]]
    )


@router.callback_query(F.data.startswith("pfopen:"))
async def admin_portfolio_open(call: CallbackQuery, session: AsyncSession):
    creator_id = int(call.data.split(":")[1])
    items = await repo.list_items(session, creator_id)
    if not items:
        await call.answer(t("portfolio_empty", Lang.ru), show_alert=True)
        return
    kb = _admin_view_kb(creator_id, 0, len(items))
    await _send_card(call.message, items[0], 1, len(items), Lang.ru, kb)
    await call.answer()


@router.callback_query(F.data.startswith("pfv:"))
async def admin_portfolio_nav(call: CallbackQuery, session: AsyncSession):
    _, cid_raw, idx_raw = call.data.split(":")
    creator_id, idx = int(cid_raw), int(idx_raw)
    items = await repo.list_items(session, creator_id)
    if not items:
        await call.answer()
        return
    idx %= len(items)
    kb = _admin_view_kb(creator_id, idx, len(items))
    await _edit_or_resend(call, items[idx], idx + 1, len(items), Lang.ru, kb)
    await call.answer()
