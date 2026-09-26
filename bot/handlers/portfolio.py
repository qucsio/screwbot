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

from bot import app_config
from bot.db.models import CreatorStatus, Lang, MediaType, User
from bot.db.repositories import portfolio as repo
from bot.db.repositories import profiles as profiles_repo
from bot.db.repositories.works import get_approved_creator, get_creator
from bot.locales import t
from bot.services.forms import cancel_kb, read_text, skip_kb
from bot.services.media import detect_media
from bot.services.moderation import direction_title
from bot.services.text import PORTFOLIO_CAPTION_MAX, esc
from bot.states.portfolio import AddPortfolio

router = Router()

_INPUT_MEDIA = {
    MediaType.photo: InputMediaPhoto,
    MediaType.video: InputMediaVideo,
    MediaType.audio: InputMediaAudio,
    MediaType.document: InputMediaDocument,
}


def _caption(item, pos: int, total: int, lang: Lang) -> str:
    tail = f"\n{esc(item.caption, limit=PORTFOLIO_CAPTION_MAX)}" if item.caption else ""
    return t("portfolio_card", lang, pos=pos, total=total, caption=tail)


def _owner_keyboard(lang: Lang, profile_id: int, item_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=t("beat_prev", lang), callback_data="portnav:prev"),
                InlineKeyboardButton(text=t("beat_next", lang), callback_data="portnav:next"),
            ],
            [InlineKeyboardButton(text=t("btn_portfolio_add", lang), callback_data=f"port:add:{profile_id}")],
            [InlineKeyboardButton(text=t("btn_portfolio_del", lang), callback_data=f"port:del:{item_id}")],
        ]
    )


def _add_only_keyboard(lang: Lang, profile_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text=t("btn_portfolio_add", lang), callback_data=f"port:add:{profile_id}")
        ]]
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
# ПОРТФОЛИО ИСПОЛНИТЕЛЯ: своё на каждое направление
# =========================================================================


async def open_portfolio(message: Message, state: FSMContext, session: AsyncSession, user: User):
    """Из панели: если направление одно — открываем сразу, иначе спрашиваем какое."""
    creator = await get_creator(session, user.id)
    profiles = await profiles_repo.list_profiles(session, creator.id) if creator else []
    if not profiles:
        await message.answer(t("portfolio_only_creator", user.lang))
        return
    if len(profiles) == 1:
        await _show_profile_portfolio(message, state, session, user, profiles[0].id)
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=direction_title(p.direction, user.lang), callback_data=f"port:open:{p.id}")]
        for p in profiles
    ])
    await message.answer(t("portfolio_choose_direction", user.lang), reply_markup=kb)


async def _show_profile_portfolio(
    target: Message, state: FSMContext, session: AsyncSession, user: User, profile_id: int
) -> None:
    creator = await get_creator(session, user.id)
    profile = await profiles_repo.get_own_profile(session, profile_id, creator.id) if creator else None
    if profile is None:
        await target.answer(t("portfolio_only_creator", user.lang))
        return
    items = await repo.list_profile_items(session, creator.id, profile.id)
    await state.update_data(port_profile=profile.id, port_ids=[i.id for i in items], port_idx=0)
    if not items:
        await target.answer(
            t("portfolio_empty_direction", user.lang, direction=direction_title(profile.direction, user.lang)),
            reply_markup=_add_only_keyboard(user.lang, profile.id),
        )
        return
    await _send_card(target, items[0], 1, len(items), user.lang,
                     _owner_keyboard(user.lang, profile.id, items[0].id))


@router.callback_query(F.data.startswith("port:open:"))
async def portfolio_open(call: CallbackQuery, state: FSMContext, session: AsyncSession, user: User):
    await _show_profile_portfolio(call.message, state, session, user, int(call.data.split(":")[2]))
    await call.answer()


@router.callback_query(F.data.in_({"portnav:prev", "portnav:next"}))
async def portfolio_nav(call: CallbackQuery, state: FSMContext, session: AsyncSession, user: User):
    creator = await get_creator(session, user.id)
    data = await state.get_data()
    ids = data.get("port_ids") or []
    if creator is None or not ids:
        await call.answer(t("button_outdated", user.lang))
        return
    idx = (data.get("port_idx", 0) + (1 if call.data.endswith("next") else -1)) % len(ids)
    item = await repo.get_item(session, ids[idx], creator.id)
    if item is None:
        await call.answer(t("button_outdated", user.lang))
        return
    await state.update_data(port_idx=idx)
    await _edit_or_resend(call, item, idx + 1, len(ids), user.lang,
                          _owner_keyboard(user.lang, data.get("port_profile", 0), item.id))
    await call.answer()


@router.callback_query(F.data.startswith("port:add:"))
async def portfolio_add(call: CallbackQuery, state: FSMContext, session: AsyncSession, user: User):
    creator = await get_creator(session, user.id)
    profile_id = int(call.data.split(":")[2])
    profile = await profiles_repo.get_own_profile(session, profile_id, creator.id) if creator else None
    if profile is None:
        await call.answer(t("portfolio_only_creator", user.lang), show_alert=True)
        return
    await state.set_state(AddPortfolio.media)
    await state.update_data(port_profile=profile.id)
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
    await message.answer(t("portfolio_caption_prompt", user.lang), reply_markup=skip_kb(user.lang, "port:nocap"))


@router.message(AddPortfolio.caption)
async def portfolio_save(message: Message, state: FSMContext, session: AsyncSession, user: User):
    if message.text is None:
        # второй файл (например, из альбома) пришёл, пока ждём подпись к первому
        await message.answer(t("portfolio_caption_need_text", user.lang),
                             reply_markup=skip_kb(user.lang, "port:nocap"))
        return
    text = await read_text(message, user.lang, PORTFOLIO_CAPTION_MAX)
    if text is None:
        return
    await _save_item(message, state, session, user, None if text == "-" else text)


@router.callback_query(AddPortfolio.caption, F.data == "port:nocap")
async def portfolio_save_no_caption(call: CallbackQuery, state: FSMContext, session: AsyncSession, user: User):
    await _save_item(call.message, state, session, user, None)
    await call.answer()


async def _save_item(target: Message, state: FSMContext, session: AsyncSession, user: User,
                     caption: str | None) -> None:
    data = await state.get_data()
    await state.set_state(None)
    creator = await get_creator(session, user.id)
    profile_id = data.get("port_profile")
    profile = await profiles_repo.get_own_profile(session, profile_id, creator.id) if creator else None
    if profile is None:
        await target.answer(t("portfolio_only_creator", user.lang))
        return
    await repo.add_item(session, creator.id, MediaType(data["pf_type"]), data["pf_file"], caption, profile.id)
    await target.answer(t("portfolio_saved", user.lang))
    await _show_profile_portfolio(target, state, session, user, profile.id)


@router.callback_query(F.data.startswith("port:del:"))
async def portfolio_delete(call: CallbackQuery, state: FSMContext, session: AsyncSession, user: User):
    creator = await get_approved_creator(session, user.id)
    if creator is None:
        await call.answer()
        return
    item_id = int(call.data.split(":")[2])
    data = await state.get_data()
    await repo.delete_item(session, item_id, creator.id)
    try:
        await call.message.delete()
    except Exception:
        pass
    await call.answer(t("portfolio_deleted", user.lang))
    if data.get("port_profile"):
        await _show_profile_portfolio(call.message, state, session, user, data["port_profile"])


# =========================================================================
# ПРОСМОТР ЧУЖОГО ПОРТФОЛИО: админ (модерация) и клиент (витрина)
# =========================================================================


async def _can_view(session: AsyncSession, scope: str, ident: int, user: User | None, tg_id: int) -> bool:
    """Человека целиком смотрит только админ; профиль — админ, владелец и, если
    он одобрен, любой клиент (это витрина для выбора исполнителя)."""
    if tg_id == app_config.ADMIN_ID:
        return True
    if scope != "p":
        return False
    bundle = await profiles_repo.profile_with_owner(session, ident)
    if bundle is None:
        return False
    profile, creator, owner = bundle
    if user is not None and owner.id == user.id:
        return True
    return profile.status == CreatorStatus.approved and creator.status == CreatorStatus.approved


async def _viewer_items(session: AsyncSession, scope: str, ident: int):
    if scope == "p":
        bundle = await profiles_repo.profile_with_owner(session, ident)
        if bundle is None:
            return []
        profile, creator, _ = bundle
        return await repo.list_profile_items(session, creator.id, profile.id)
    return await repo.list_items(session, ident)


def _viewer_kb(scope: str, ident: int, idx: int, total: int, lang: Lang) -> InlineKeyboardMarkup:
    prev_idx, next_idx = (idx - 1) % total, (idx + 1) % total
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t("beat_prev", lang), callback_data=f"pfv:{scope}:{ident}:{prev_idx}"),
        InlineKeyboardButton(text=t("beat_next", lang), callback_data=f"pfv:{scope}:{ident}:{next_idx}"),
    ]])


@router.callback_query(F.data.startswith("pfopen:"))
async def portfolio_open_creator(call: CallbackQuery, session: AsyncSession, user: User | None):
    await _open_viewer(call, session, user, "c", int(call.data.split(":")[1]))


@router.callback_query(F.data.startswith("pfprof:"))
async def portfolio_open_profile(call: CallbackQuery, session: AsyncSession, user: User | None):
    await _open_viewer(call, session, user, "p", int(call.data.split(":")[1]))


async def _open_viewer(call: CallbackQuery, session: AsyncSession, user: User | None, scope: str, ident: int):
    lang = user.lang if user else Lang.ru
    if not await _can_view(session, scope, ident, user, call.from_user.id):
        await call.answer(t("button_outdated", lang))
        return
    items = await _viewer_items(session, scope, ident)
    if not items:
        await call.answer(t("portfolio_empty", lang), show_alert=True)
        return
    await _send_card(call.message, items[0], 1, len(items), lang, _viewer_kb(scope, ident, 0, len(items), lang))
    await call.answer()


@router.callback_query(F.data.startswith("pfv:"))
async def portfolio_view_nav(call: CallbackQuery, session: AsyncSession, user: User | None):
    lang = user.lang if user else Lang.ru
    parts = call.data.split(":")
    # старый формат кнопки (до разделения на направления) или мусор — не падаем
    if len(parts) != 4 or not parts[2].isdigit() or not parts[3].isdigit():
        await call.answer(t("button_outdated", lang))
        return
    scope, ident, idx = parts[1], int(parts[2]), int(parts[3])
    if not await _can_view(session, scope, ident, user, call.from_user.id):
        await call.answer(t("button_outdated", lang))
        return
    items = await _viewer_items(session, scope, ident)
    if not items:
        await call.answer(t("portfolio_empty", lang), show_alert=True)
        return
    idx %= len(items)
    await _edit_or_resend(call, items[idx], idx + 1, len(items), lang,
                          _viewer_kb(scope, ident, idx, len(items), lang))
    await call.answer()
