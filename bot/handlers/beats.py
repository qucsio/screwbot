from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InputMediaPhoto, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.categories import by_code
from bot.db.models import Creator, Lang, ModerationStatus, User, Work
from bot.db.repositories import works as repo
from bot.keyboards.common import (
    filter_intro_keyboard,
    genre_keyboard,
    work_card_keyboard,
    work_moderation_keyboard,
)
from bot.locales import t
from bot.services.notify import notify_admin, send_work_to_moderation
from bot.states.beats import AddBeat, AddVisual, BeatFilter

router = Router()

READY_BEATS = "ready_beats"
READY_VISUAL = "ready_visual"


class BeatQuestion(StatesGroup):
    waiting = State()


def _contact(user: User) -> str:
    return f"@{user.username}" if user.username else f"id{user.tg_id}"


def _money(v) -> str:
    return f"{v:g}" if v is not None else "—"


# =========================================================================
# ЗАГРУЗКА БИТА (исполнитель)
# =========================================================================


@router.message(Command("addbeat"))
async def addbeat_start(
    message: Message, state: FSMContext, session: AsyncSession, user: User | None
):
    if user is None:
        return
    creator = await repo.get_approved_creator(session, user.id)
    if creator is None:
        await message.answer(t("addbeat_only_creator", user.lang))
        return
    await state.clear()
    await state.set_state(AddBeat.title)
    await message.answer(t("addbeat_title", user.lang))


@router.message(AddBeat.title)
async def addbeat_title(message: Message, state: FSMContext, user: User):
    await state.update_data(title=message.text.strip()[:128])
    await state.set_state(AddBeat.genre)
    await message.answer(t("addbeat_genre", user.lang))


@router.message(AddBeat.genre)
async def addbeat_genre(message: Message, state: FSMContext, user: User):
    await state.update_data(genre=message.text.strip()[:64])
    await state.set_state(AddBeat.key)
    await message.answer(t("addbeat_key", user.lang))


@router.message(AddBeat.key)
async def addbeat_key(message: Message, state: FSMContext, user: User):
    await state.update_data(key=message.text.strip()[:16])
    await state.set_state(AddBeat.bpm)
    await message.answer(t("addbeat_bpm", user.lang))


@router.message(AddBeat.bpm)
async def addbeat_bpm(message: Message, state: FSMContext, user: User):
    if not (message.text or "").strip().isdigit():
        await message.answer(t("addbeat_bpm_invalid", user.lang))
        return
    await state.update_data(bpm=int(message.text.strip()))
    await state.set_state(AddBeat.cover)
    await message.answer(t("addbeat_cover", user.lang))


@router.message(AddBeat.cover, F.photo)
async def addbeat_cover(message: Message, state: FSMContext, user: User):
    await state.update_data(cover_file_id=message.photo[-1].file_id)
    await state.set_state(AddBeat.audio)
    await message.answer(t("addbeat_audio", user.lang))


@router.message(AddBeat.cover)
async def addbeat_cover_invalid(message: Message, user: User):
    await message.answer(t("addbeat_cover_invalid", user.lang))


@router.message(AddBeat.audio, F.audio | F.voice | F.document)
async def addbeat_audio(message: Message, state: FSMContext, user: User):
    file = message.audio or message.voice or message.document
    await state.update_data(audio_file_id=file.file_id)
    await state.set_state(AddBeat.price_rent)
    await message.answer(t("addbeat_price_rent", user.lang))


@router.message(AddBeat.audio)
async def addbeat_audio_invalid(message: Message, user: User):
    await message.answer(t("addbeat_audio_invalid", user.lang))


@router.message(AddBeat.price_rent)
async def addbeat_price_rent(message: Message, state: FSMContext, user: User):
    price = _parse_price(message.text)
    if price is None:
        await message.answer(t("addbeat_price_invalid", user.lang))
        return
    await state.update_data(price_rent=price)
    await state.set_state(AddBeat.price_buy)
    await message.answer(t("addbeat_price_buy", user.lang))


@router.message(AddBeat.price_buy)
async def addbeat_price_buy(
    message: Message, state: FSMContext, session: AsyncSession, user: User, bot: Bot
):
    price = _parse_price(message.text)
    if price is None:
        await message.answer(t("addbeat_price_invalid", user.lang))
        return
    data = await state.get_data()
    creator, direct = await _resolve_creator(session, data, user)
    if creator is None:
        await state.clear()
        return
    category = await repo.get_category_by_code(session, READY_BEATS)

    work = Work(
        creator_id=creator.id,
        category_id=category.id,
        title=data["title"],
        cover_file_id=data["cover_file_id"],
        audio_file_id=data["audio_file_id"],
        genre=data["genre"],
        key=data["key"],
        bpm=data["bpm"],
        price_rent=data["price_rent"],
        price_buy=price,
        moderation_status=ModerationStatus.approved if direct else ModerationStatus.pending,
    )
    session.add(work)
    await session.commit()
    await state.clear()

    if direct:
        await message.answer(t("adm_work_added_direct", Lang.ru))
        return

    await message.answer(t("addbeat_sent", user.lang))
    card = t(
        "mod_new_beat", Lang.ru,
        author=_contact(user), title=work.title,
        genre=work.genre, key=work.key, bpm=work.bpm,
        rent=_money(work.price_rent), buy=_money(work.price_buy),
    )
    await send_work_to_moderation(
        bot, card, work.cover_file_id,
        work_moderation_keyboard(Lang.ru, work.id, creator.id),
        audio_file_id=work.audio_file_id,
    )


async def _resolve_creator(session: AsyncSession, data: dict, user: User):
    """Возвращает (creator, direct): direct=True если грузит админ за автора."""
    target = data.get("target_creator_id")
    if target:
        return await session.get(Creator, target), True
    return await repo.get_approved_creator(session, user.id), False


def _parse_price(text: str | None):
    if not text:
        return None
    cleaned = text.strip().replace(" ", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


# =========================================================================
# ДОБАВИТЬ РАБОТУ (выбор типа) + ЗАГРУЗКА ВИЗУАЛА
# =========================================================================


def _add_work_keyboard(lang: Lang):
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t("addwork_beat", lang), callback_data="addwork:beat"),
        InlineKeyboardButton(text=t("addwork_visual", lang), callback_data="addwork:visual"),
    ]])


async def open_add_work(message: Message, session: AsyncSession, user: User):
    creator = await repo.get_approved_creator(session, user.id)
    if creator is None:
        await message.answer(t("addwork_only_creator", user.lang))
        return
    await message.answer(t("addwork_choose", user.lang), reply_markup=_add_work_keyboard(user.lang))


@router.message(Command("addwork"))
async def add_work_start(message: Message, session: AsyncSession, user: User | None):
    if user is None:
        return
    await open_add_work(message, session, user)


@router.callback_query(F.data == "addwork:beat")
async def add_work_beat(call: CallbackQuery, state: FSMContext, session: AsyncSession, user: User):
    creator = await repo.get_approved_creator(session, user.id)
    if creator is None:
        await call.answer(t("addwork_only_creator", user.lang), show_alert=True)
        return
    await state.clear()
    await state.set_state(AddBeat.title)
    await call.message.answer(t("addbeat_title", user.lang))
    await call.answer()


@router.callback_query(F.data == "addwork:visual")
async def add_work_visual(call: CallbackQuery, state: FSMContext, session: AsyncSession, user: User):
    creator = await repo.get_approved_creator(session, user.id)
    if creator is None:
        await call.answer(t("addwork_only_creator", user.lang), show_alert=True)
        return
    await state.clear()
    await state.set_state(AddVisual.title)
    await call.message.answer(t("addvisual_title", user.lang))
    await call.answer()


@router.message(AddVisual.title)
async def addvisual_title(message: Message, state: FSMContext, user: User):
    await state.update_data(title=message.text.strip()[:128])
    await state.set_state(AddVisual.vtype)
    await message.answer(t("addvisual_type", user.lang))


@router.message(AddVisual.vtype)
async def addvisual_type(message: Message, state: FSMContext, user: User):
    await state.update_data(vtype=message.text.strip()[:64])
    await state.set_state(AddVisual.cover)
    await message.answer(t("addvisual_cover", user.lang))


@router.message(AddVisual.cover, F.photo)
async def addvisual_cover(message: Message, state: FSMContext, user: User):
    await state.update_data(cover_file_id=message.photo[-1].file_id)
    await state.set_state(AddVisual.price_buy)
    await message.answer(t("addvisual_price_buy", user.lang))


@router.message(AddVisual.cover)
async def addvisual_cover_invalid(message: Message, user: User):
    await message.answer(t("addvisual_cover_invalid", user.lang))


@router.message(AddVisual.price_buy)
async def addvisual_price_buy(
    message: Message, state: FSMContext, session: AsyncSession, user: User, bot: Bot
):
    price = _parse_price(message.text)
    if price is None:
        await message.answer(t("addbeat_price_invalid", user.lang))
        return
    data = await state.get_data()
    creator, direct = await _resolve_creator(session, data, user)
    if creator is None:
        await state.clear()
        return
    category = await repo.get_category_by_code(session, READY_VISUAL)

    work = Work(
        creator_id=creator.id,
        category_id=category.id,
        title=data["title"],
        cover_file_id=data["cover_file_id"],
        genre=data["vtype"],          # тип визуала храним в genre
        price_buy=price,
        moderation_status=ModerationStatus.approved if direct else ModerationStatus.pending,
    )
    session.add(work)
    await session.commit()
    await state.clear()

    if direct:
        await message.answer(t("adm_work_added_direct", Lang.ru))
        return

    await message.answer(t("addvisual_sent", user.lang))
    card = t(
        "mod_new_visual", Lang.ru,
        author=_contact(user), title=work.title,
        vtype=work.genre, buy=_money(work.price_buy),
    )
    await send_work_to_moderation(
        bot, card, work.cover_file_id,
        work_moderation_keyboard(Lang.ru, work.id, creator.id),
    )


# =========================================================================
# МОДЕРАЦИЯ РАБОТЫ
# =========================================================================


@router.callback_query(F.data.startswith("modwork:"))
async def moderate_work(call: CallbackQuery, session: AsyncSession, bot: Bot):
    _, action, work_id_raw = call.data.split(":")
    pair = await repo.get_work_with_author(session, int(work_id_raw))
    if pair is None:
        await call.answer("not found", show_alert=True)
        return
    work, author = pair

    if action == "approve":
        work.moderation_status = ModerationStatus.approved
        admin_msg = t("mod_approved_admin", Lang.ru)
        notify = t("work_approved_notify", author.lang, title=work.title)
    else:
        work.moderation_status = ModerationStatus.rejected
        admin_msg = t("mod_rejected_admin", Lang.ru)
        notify = t("work_rejected_notify", author.lang, title=work.title)
    await session.commit()

    try:
        await bot.send_message(author.tg_id, notify)
    except Exception:
        pass

    # карточка может быть фото (с подписью) или текстом
    try:
        if call.message.caption is not None:
            await call.message.edit_caption(caption=f"{call.message.caption}\n\n— {admin_msg}")
        else:
            await call.message.edit_text(f"{call.message.text}\n\n— {admin_msg}")
    except Exception:
        pass
    await call.answer(admin_msg)


# =========================================================================
# КАТАЛОГ + ФИЛЬТР + КАРУСЕЛЬ (клиент)
# =========================================================================


async def open_catalog(
    message: Message, state: FSMContext, session: AsyncSession, user: User, code: str = READY_BEATS
):
    """Точка входа из меню каталога (биты/визуалы) — универсально по коду."""
    category = await repo.get_category_by_code(session, code)
    if category is None:
        await message.answer(t("catalog_empty", user.lang))
        return
    ids = await repo.filter_beats(session, category.id)
    if not ids:
        await message.answer(t("catalog_empty", user.lang))
        return
    ctype = (by_code(code).catalog_type if by_code(code) else "beat") or "beat"
    await state.clear()
    await state.update_data(category_id=category.id, ctype=ctype)
    await message.answer(t("filter_intro", user.lang), reply_markup=filter_intro_keyboard(user.lang))


@router.callback_query(F.data == "beatflt:all")
async def filter_all(call: CallbackQuery, state: FSMContext, session: AsyncSession, user: User):
    data = await state.get_data()
    ids = await repo.filter_beats(session, data["category_id"])
    await _start_carousel(call, state, session, user, ids)
    await call.answer()


@router.callback_query(F.data == "beatflt:setup")
async def filter_setup(call: CallbackQuery, state: FSMContext, session: AsyncSession, user: User):
    data = await state.get_data()
    genres = await repo.approved_beat_genres(session, data["category_id"])
    is_visual = data.get("ctype") == "visual"
    await state.set_state(BeatFilter.genre)
    await call.message.edit_text(
        t("filter_type" if is_visual else "filter_genre", user.lang),
        reply_markup=genre_keyboard(user.lang, genres),
    )
    await call.answer()


@router.callback_query(BeatFilter.genre, F.data.startswith("fltgenre:"))
async def filter_pick_genre(call: CallbackQuery, state: FSMContext, session: AsyncSession, user: User):
    genre = call.data.split(":", 1)[1]
    await state.update_data(f_genre=None if genre == "__any__" else genre)
    data = await state.get_data()
    # у визуалов фильтр только по типу — сразу показываем результаты
    if data.get("ctype") == "visual":
        ids = await repo.filter_beats(session, data["category_id"], genre=data.get("f_genre"))
        if not ids:
            await state.set_state(None)
            await call.message.edit_text(t("filter_no_results", user.lang))
        else:
            await _start_carousel(call, state, session, user, ids)
        await call.answer()
        return
    await state.set_state(BeatFilter.key)
    await call.message.edit_text(t("filter_key", user.lang))
    await call.answer()


@router.message(BeatFilter.key)
async def filter_key(message: Message, state: FSMContext, user: User):
    val = message.text.strip()
    await state.update_data(f_key=None if val == "-" else val[:16])
    await state.set_state(BeatFilter.bpm)
    await message.answer(t("filter_bpm", user.lang))


@router.message(BeatFilter.bpm)
async def filter_bpm(message: Message, state: FSMContext, session: AsyncSession, user: User):
    bpm_min = bpm_max = None
    val = message.text.strip()
    if val != "-" and "-" in val:
        lo, _, hi = val.partition("-")
        if lo.strip().isdigit():
            bpm_min = int(lo.strip())
        if hi.strip().isdigit():
            bpm_max = int(hi.strip())
    data = await state.get_data()
    ids = await repo.filter_beats(
        session, data["category_id"],
        genre=data.get("f_genre"), key=data.get("f_key"),
        bpm_min=bpm_min, bpm_max=bpm_max,
    )
    if not ids:
        await state.set_state(None)
        await message.answer(t("filter_no_results", user.lang))
        return
    await _start_carousel(message, state, session, user, ids)


async def _render_caption(session: AsyncSession, work_id: int, pos: int, total: int, lang: Lang, ctype: str):
    pair = await repo.get_work_with_author(session, work_id)
    work, author = pair
    if ctype == "visual":
        caption = t(
            "visual_card", lang,
            title=work.title, author=_contact(author),
            vtype=work.genre or "—", buy=_money(work.price_buy),
            pos=pos, total=total,
        )
    else:
        caption = t(
            "beat_card", lang,
            title=work.title, author=_contact(author),
            genre=work.genre or "—", key=work.key or "—", bpm=work.bpm or "—",
            rent=_money(work.price_rent), buy=_money(work.price_buy),
            pos=pos, total=total,
        )
    return work, caption


async def _start_carousel(event, state: FSMContext, session: AsyncSession, user: User, ids: list[int]):
    await state.set_state(None)
    data = await state.get_data()
    ctype = data.get("ctype", "beat")
    await state.update_data(beat_ids=ids, beat_idx=0)
    work, caption = await _render_caption(session, ids[0], 1, len(ids), user.lang, ctype)
    target = event.message if isinstance(event, CallbackQuery) else event
    await target.answer_photo(
        work.cover_file_id,
        caption=caption,
        reply_markup=work_card_keyboard(user.lang, work.id, ctype),
    )


@router.callback_query(F.data.in_({"beatnav:prev", "beatnav:next"}))
async def carousel_nav(call: CallbackQuery, state: FSMContext, session: AsyncSession, user: User):
    data = await state.get_data()
    ids = data.get("beat_ids") or []
    if not ids:
        await call.answer()
        return
    ctype = data.get("ctype", "beat")
    idx = data.get("beat_idx", 0)
    idx = (idx + (1 if call.data.endswith("next") else -1)) % len(ids)
    await state.update_data(beat_idx=idx)
    work, caption = await _render_caption(session, ids[idx], idx + 1, len(ids), user.lang, ctype)
    await call.message.edit_media(
        InputMediaPhoto(media=work.cover_file_id, caption=caption),
        reply_markup=work_card_keyboard(user.lang, work.id, ctype),
    )
    await call.answer()


@router.callback_query(F.data.startswith("beat:listen:"))
async def beat_listen(call: CallbackQuery, session: AsyncSession, user: User):
    work_id = int(call.data.split(":")[2])
    pair = await repo.get_work_with_author(session, work_id)
    if pair and pair[0].audio_file_id:
        await call.message.answer_audio(pair[0].audio_file_id, title=pair[0].title)
    await call.answer()


@router.callback_query(F.data.startswith("beat:buy:"))
async def beat_buy(call: CallbackQuery, session: AsyncSession, user: User, bot: Bot):
    work_id = int(call.data.split(":")[2])
    pair = await repo.get_work_with_author(session, work_id)
    if pair is None:
        await call.answer()
        return
    work, author = pair
    text = t(
        "mod_beat_buy", Lang.ru,
        title=work.title, work_id=work.id,
        contact=_contact(user), author=_contact(author),
        rent=_money(work.price_rent), buy=_money(work.price_buy),
    )
    await notify_admin(bot, text)
    await call.answer(t("beat_buy_sent", user.lang), show_alert=True)


@router.callback_query(F.data.startswith("beat:ask:"))
async def beat_ask(call: CallbackQuery, state: FSMContext, session: AsyncSession, user: User):
    work_id = int(call.data.split(":")[2])
    pair = await repo.get_work_with_author(session, work_id)
    title = pair[0].title if pair else "—"
    await state.set_state(BeatQuestion.waiting)
    await state.update_data(ask_work_id=work_id, ask_title=title)
    await call.message.answer(t("beat_ask_prompt", user.lang, title=title))
    await call.answer()


@router.message(BeatQuestion.waiting)
async def beat_ask_send(message: Message, state: FSMContext, user: User, bot: Bot):
    data = await state.get_data()
    text = t(
        "mod_beat_question", Lang.ru,
        title=data.get("ask_title", "—"), work_id=data.get("ask_work_id"),
        contact=_contact(user), text=message.text or "—",
    )
    await notify_admin(bot, text)
    await state.set_state(None)
    await message.answer(t("beat_ask_sent", user.lang))
