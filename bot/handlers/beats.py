from decimal import Decimal

from aiogram import Bot, F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InputMediaPhoto, InputMediaVideo, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot import app_config
from bot.categories import by_code
from bot.db.models import Creator, Lang, ModerationStatus, User, Work
from bot.db.repositories import works as repo
from bot.filters import IsAdmin
from bot.keyboards.common import (
    filter_intro_keyboard,
    genre_keyboard,
    work_card_keyboard,
)
from bot.locales import t
from bot.services.forms import cancel_kb, guard_text, read_text, skip_kb, step
from bot.services.media import detect_audio, send_work_audio
from bot.services.moderation import send_work_card
from bot.services.money import fmt_money, parse_money
from bot.services.notify import notify_admin
from bot.services.order_view import contact
from bot.services.text import GENRE_MAX, KEY_MAX, QUESTION_MAX, TITLE_MAX, esc
from bot.states.beats import AddBeat, AddVideo, AddVisual, BeatFilter

_BEAT_STEPS = 8
_VISUAL_STEPS = 4
_VIDEO_STEPS = 4
# Пределы темпа: отсекают опечатки вроде «0» или «14000».
BPM_MIN, BPM_MAX = 1, 999

router = Router()

READY_BEATS = "ready_beats"
READY_VISUAL = "ready_visual"
READY_VIDEO = "ready_video"

# Каталоги с одной характеристикой-типом и фильтром только по типу.
_SINGLE_FIELD_TYPES = ("visual", "video")


class BeatQuestion(StatesGroup):
    waiting = State()


def _contact(user: User) -> str:
    """Автор в публичной карточке каталога."""
    return f"@{user.username}" if user.username else f"id{user.tg_id}"


def parse_bpm(text: str | None) -> int | None:
    raw = (text or "").strip()
    if not raw.isdigit():
        return None
    bpm = int(raw)
    return bpm if BPM_MIN <= bpm <= BPM_MAX else None


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
    await message.answer(step(1, _BEAT_STEPS, "addbeat_title", user.lang), reply_markup=cancel_kb(user.lang))


@router.message(AddBeat.title)
async def addbeat_title(message: Message, state: FSMContext, user: User):
    value = await read_text(message, user.lang, TITLE_MAX)
    if value is None:
        return
    await state.update_data(title=value)
    await state.set_state(AddBeat.genre)
    await message.answer(step(2, _BEAT_STEPS, "addbeat_genre", user.lang), reply_markup=cancel_kb(user.lang))


@router.message(AddBeat.genre)
async def addbeat_genre(message: Message, state: FSMContext, user: User):
    value = await read_text(message, user.lang, GENRE_MAX)
    if value is None:
        return
    await state.update_data(genre=value)
    await state.set_state(AddBeat.key)
    await message.answer(step(3, _BEAT_STEPS, "addbeat_key", user.lang), reply_markup=cancel_kb(user.lang))


@router.message(AddBeat.key)
async def addbeat_key(message: Message, state: FSMContext, user: User):
    value = await read_text(message, user.lang, KEY_MAX)
    if value is None:
        return
    await state.update_data(key=value)
    await state.set_state(AddBeat.bpm)
    await message.answer(step(4, _BEAT_STEPS, "addbeat_bpm", user.lang), reply_markup=cancel_kb(user.lang))


@router.message(AddBeat.bpm)
async def addbeat_bpm(message: Message, state: FSMContext, user: User):
    bpm = parse_bpm(message.text)
    if bpm is None:
        await message.answer(t("addbeat_bpm_invalid", user.lang), reply_markup=cancel_kb(user.lang))
        return
    await state.update_data(bpm=bpm)
    await state.set_state(AddBeat.cover)
    await message.answer(step(5, _BEAT_STEPS, "addbeat_cover", user.lang), reply_markup=cancel_kb(user.lang))


@router.message(AddBeat.cover, F.photo)
async def addbeat_cover(message: Message, state: FSMContext, user: User):
    await state.update_data(cover_file_id=message.photo[-1].file_id)
    await state.set_state(AddBeat.audio)
    await message.answer(step(6, _BEAT_STEPS, "addbeat_audio", user.lang), reply_markup=cancel_kb(user.lang))


@router.message(AddBeat.cover)
async def addbeat_cover_invalid(message: Message, user: User):
    await message.answer(t("addbeat_cover_invalid", user.lang), reply_markup=cancel_kb(user.lang))


@router.message(AddBeat.audio)
async def addbeat_audio(message: Message, state: FSMContext, user: User):
    # Только аудио: голосовое или PDF раньше принимались, а потом «Слушать» падала.
    found = detect_audio(message)
    if found is None:
        await message.answer(t("addbeat_audio_invalid", user.lang), reply_markup=cancel_kb(user.lang))
        return
    kind, file_id = found
    await state.update_data(audio_file_id=file_id, audio_kind=kind)
    await state.set_state(AddBeat.price_rent)
    await message.answer(step(7, _BEAT_STEPS, "addbeat_price_rent", user.lang), reply_markup=cancel_kb(user.lang))


@router.message(AddBeat.price_rent)
async def addbeat_price_rent(message: Message, state: FSMContext, user: User):
    price = parse_money(message.text, allow_zero=True)
    if price is None:
        await message.answer(t("addbeat_price_invalid", user.lang), reply_markup=cancel_kb(user.lang))
        return
    # Данные формы лежат в Redis как JSON — Decimal туда не пройдёт, храним строкой.
    await state.update_data(price_rent=str(price))
    await state.set_state(AddBeat.price_buy)
    await message.answer(step(8, _BEAT_STEPS, "addbeat_price_buy", user.lang), reply_markup=cancel_kb(user.lang))


@router.message(AddBeat.price_buy)
async def addbeat_price_buy(
    message: Message, state: FSMContext, session: AsyncSession, user: User, bot: Bot
):
    price = parse_money(message.text, allow_zero=True)
    if price is None:
        await message.answer(t("addbeat_price_invalid", user.lang), reply_markup=cancel_kb(user.lang))
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
        audio_kind=data.get("audio_kind"),
        genre=data["genre"],
        key=data["key"],
        bpm=data["bpm"],
        price_rent=Decimal(str(data["price_rent"])),
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
    await send_work_card(bot, work, user, "beat")


async def _resolve_creator(session: AsyncSession, data: dict, user: User):
    """Возвращает (creator, direct): direct=True если грузит админ за автора."""
    target = data.get("target_creator_id")
    if target:
        return await session.get(Creator, target), True
    return await repo.get_approved_creator(session, user.id), False


# =========================================================================
# ДОБАВИТЬ РАБОТУ (выбор типа) + ЗАГРУЗКА ВИЗУАЛА
# =========================================================================


def _add_work_keyboard(lang: Lang):
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t("addwork_beat", lang), callback_data="addwork:beat"),
        InlineKeyboardButton(text=t("addwork_visual", lang), callback_data="addwork:visual"),
        InlineKeyboardButton(text=t("addwork_video", lang), callback_data="addwork:video"),
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
    await call.message.answer(step(1, _BEAT_STEPS, "addbeat_title", user.lang), reply_markup=cancel_kb(user.lang))
    await call.answer()


@router.callback_query(F.data == "addwork:visual")
async def add_work_visual(call: CallbackQuery, state: FSMContext, session: AsyncSession, user: User):
    creator = await repo.get_approved_creator(session, user.id)
    if creator is None:
        await call.answer(t("addwork_only_creator", user.lang), show_alert=True)
        return
    await state.clear()
    await state.set_state(AddVisual.title)
    await call.message.answer(step(1, _VISUAL_STEPS, "addvisual_title", user.lang), reply_markup=cancel_kb(user.lang))
    await call.answer()


@router.message(AddVisual.title)
async def addvisual_title(message: Message, state: FSMContext, user: User):
    value = await read_text(message, user.lang, TITLE_MAX)
    if value is None:
        return
    await state.update_data(title=value)
    await state.set_state(AddVisual.vtype)
    await message.answer(step(2, _VISUAL_STEPS, "addvisual_type", user.lang), reply_markup=cancel_kb(user.lang))


@router.message(AddVisual.vtype)
async def addvisual_type(message: Message, state: FSMContext, user: User):
    value = await read_text(message, user.lang, GENRE_MAX)
    if value is None:
        return
    await state.update_data(vtype=value)
    await state.set_state(AddVisual.cover)
    await message.answer(step(3, _VISUAL_STEPS, "addvisual_cover", user.lang), reply_markup=cancel_kb(user.lang))


@router.message(AddVisual.cover, F.photo)
async def addvisual_cover(message: Message, state: FSMContext, user: User):
    await state.update_data(cover_file_id=message.photo[-1].file_id)
    await state.set_state(AddVisual.price_buy)
    await message.answer(step(4, _VISUAL_STEPS, "addvisual_price_buy", user.lang), reply_markup=cancel_kb(user.lang))


@router.message(AddVisual.cover)
async def addvisual_cover_invalid(message: Message, user: User):
    await message.answer(t("addvisual_cover_invalid", user.lang), reply_markup=cancel_kb(user.lang))


@router.message(AddVisual.price_buy)
async def addvisual_price_buy(
    message: Message, state: FSMContext, session: AsyncSession, user: User, bot: Bot
):
    price = parse_money(message.text, allow_zero=True)
    if price is None:
        await message.answer(t("addbeat_price_invalid", user.lang), reply_markup=cancel_kb(user.lang))
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
    await send_work_card(bot, work, user, "visual")


# =========================================================================
# ЗАГРУЗКА ВИДЕО (исполнитель)
# =========================================================================


@router.callback_query(F.data == "addwork:video")
async def add_work_video(call: CallbackQuery, state: FSMContext, session: AsyncSession, user: User):
    creator = await repo.get_approved_creator(session, user.id)
    if creator is None:
        await call.answer(t("addwork_only_creator", user.lang), show_alert=True)
        return
    await state.clear()
    await state.set_state(AddVideo.title)
    await call.message.answer(step(1, _VIDEO_STEPS, "addvideo_title", user.lang), reply_markup=cancel_kb(user.lang))
    await call.answer()


@router.message(AddVideo.title)
async def addvideo_title(message: Message, state: FSMContext, user: User):
    value = await read_text(message, user.lang, TITLE_MAX)
    if value is None:
        return
    await state.update_data(title=value)
    await state.set_state(AddVideo.vtype)
    await message.answer(step(2, _VIDEO_STEPS, "addvideo_type", user.lang), reply_markup=cancel_kb(user.lang))


@router.message(AddVideo.vtype)
async def addvideo_type(message: Message, state: FSMContext, user: User):
    value = await read_text(message, user.lang, GENRE_MAX)
    if value is None:
        return
    await state.update_data(vtype=value)
    await state.set_state(AddVideo.video)
    await message.answer(step(3, _VIDEO_STEPS, "addvideo_file", user.lang), reply_markup=cancel_kb(user.lang))


@router.message(AddVideo.video, F.video)
async def addvideo_file(message: Message, state: FSMContext, user: User):
    await state.update_data(cover_file_id=message.video.file_id)
    await state.set_state(AddVideo.price_buy)
    await message.answer(step(4, _VIDEO_STEPS, "addvideo_price_buy", user.lang), reply_markup=cancel_kb(user.lang))


@router.message(AddVideo.video)
async def addvideo_file_invalid(message: Message, user: User):
    await message.answer(t("addvideo_file_invalid", user.lang), reply_markup=cancel_kb(user.lang))


@router.message(AddVideo.price_buy)
async def addvideo_price_buy(
    message: Message, state: FSMContext, session: AsyncSession, user: User, bot: Bot
):
    price = parse_money(message.text, allow_zero=True)
    if price is None:
        await message.answer(t("addbeat_price_invalid", user.lang), reply_markup=cancel_kb(user.lang))
        return
    data = await state.get_data()
    creator, direct = await _resolve_creator(session, data, user)
    if creator is None:
        await state.clear()
        return
    category = await repo.get_category_by_code(session, READY_VIDEO)

    work = Work(
        creator_id=creator.id,
        category_id=category.id,
        title=data["title"],
        cover_file_id=data["cover_file_id"],   # file_id видео храним здесь
        genre=data["vtype"],                   # тип видео храним в genre
        price_buy=price,
        moderation_status=ModerationStatus.approved if direct else ModerationStatus.pending,
    )
    session.add(work)
    await session.commit()
    await state.clear()

    if direct:
        await message.answer(t("adm_work_added_direct", Lang.ru))
        return

    await message.answer(t("addvideo_sent", user.lang))
    await send_work_card(bot, work, user, "video")


# =========================================================================
# МОДЕРАЦИЯ РАБОТЫ
# =========================================================================


# IsAdmin: callback_data можно подделать и одобрить свою же работу.
@router.callback_query(F.data.startswith("modwork:"), IsAdmin())
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
        notify = t("work_approved_notify", author.lang, title=esc(work.title))
    else:
        work.moderation_status = ModerationStatus.rejected
        admin_msg = t("mod_rejected_admin", Lang.ru)
        notify = t("work_rejected_notify", author.lang, title=esc(work.title))
    await session.commit()

    try:
        await bot.send_message(author.tg_id, notify)
    except Exception:
        pass

    # карточка может быть фото (с подписью) или текстом; html_text берёт и подпись,
    # и текст с сохранением разметки и экранированием
    try:
        if call.message.caption is not None:
            await call.message.edit_caption(caption=f"{call.message.html_text}\n\n— {admin_msg}")
        else:
            await call.message.edit_text(f"{call.message.html_text}\n\n— {admin_msg}")
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
    if "category_id" not in data:
        # кнопка из старого сообщения: каталог с тех пор закрыт (раньше тут падало)
        await call.answer(t("button_outdated", user.lang))
        return
    ids = await repo.filter_beats(session, data["category_id"])
    if not ids:
        await call.answer(t("catalog_empty", user.lang), show_alert=True)
        return
    await _start_carousel(call, state, session, user, ids)
    await call.answer()


@router.callback_query(F.data == "beatflt:setup")
async def filter_setup(call: CallbackQuery, state: FSMContext, session: AsyncSession, user: User):
    data = await state.get_data()
    if "category_id" not in data:
        await call.answer(t("button_outdated", user.lang))
        return
    genres = await repo.approved_beat_genres(session, data["category_id"])
    single_field = data.get("ctype") in _SINGLE_FIELD_TYPES
    await state.set_state(BeatFilter.genre)
    # в кнопках — индексы жанров (лимит callback_data 64 байта), сами жанры — тут
    await state.update_data(f_genres=genres)
    await call.message.edit_text(
        t("filter_type" if single_field else "filter_genre", user.lang),
        reply_markup=genre_keyboard(user.lang, genres),
    )
    await call.answer()


@router.callback_query(BeatFilter.genre, F.data.startswith("fltgenre:"))
async def filter_pick_genre(call: CallbackQuery, state: FSMContext, session: AsyncSession, user: User):
    raw = call.data.split(":", 1)[1]
    data = await state.get_data()
    genre = None
    if raw != "__any__":
        genres = data.get("f_genres") or []
        idx = int(raw) if raw.isdigit() else -1
        if not 0 <= idx < len(genres):
            await call.answer()
            return
        genre = genres[idx]
    await state.update_data(f_genre=genre)
    # у визуалов и видео фильтр только по типу — сразу показываем результаты
    if data.get("ctype") in _SINGLE_FIELD_TYPES:
        await _run_filter(call.message, state, session, user, None, None)
        await call.answer()
        return
    await state.set_state(BeatFilter.key)
    await call.message.edit_text(t("filter_key", user.lang), reply_markup=skip_kb(user.lang, "fltskip"))
    await call.answer()


@router.message(BeatFilter.key)
async def filter_key(message: Message, state: FSMContext, user: User):
    val = await read_text(message, user.lang, KEY_MAX)
    if val is None:
        return
    await state.update_data(f_key=None if val == "-" else val)
    await _ask_bpm(message, state, user)


async def _ask_bpm(target: Message, state: FSMContext, user: User) -> None:
    await state.set_state(BeatFilter.bpm)
    await target.answer(t("filter_bpm", user.lang), reply_markup=skip_kb(user.lang, "fltskip"))


def _parse_bpm_range(val: str | None) -> tuple[int | None, int | None] | None:
    """«-» → без фильтра, «120-140» → диапазон, «140» → ровно 140; None — не разобрали.

    Раньше одно число молча игнорировалось и показывались все биты.
    """
    if val is None:
        return None
    val = val.replace(" ", "")
    if val == "-":
        return None, None
    if val.isdigit():
        return int(val), int(val)
    lo, sep, hi = val.partition("-")
    if not sep or not (lo or hi) or (lo and not lo.isdigit()) or (hi and not hi.isdigit()):
        return None
    lo_n, hi_n = (int(lo) if lo else None), (int(hi) if hi else None)
    if lo_n is not None and hi_n is not None and lo_n > hi_n:
        lo_n, hi_n = hi_n, lo_n
    return lo_n, hi_n


@router.message(BeatFilter.bpm)
async def filter_bpm(message: Message, state: FSMContext, session: AsyncSession, user: User):
    rng = _parse_bpm_range(guard_text(message))
    if rng is None:
        await message.answer(t("filter_bpm", user.lang), reply_markup=skip_kb(user.lang, "fltskip"))
        return
    await _run_filter(message, state, session, user, *rng)


@router.callback_query(StateFilter(BeatFilter.key, BeatFilter.bpm), F.data == "fltskip")
async def filter_skip(call: CallbackQuery, state: FSMContext, session: AsyncSession, user: User):
    """Кнопка «Пропустить» вместо набора «-»."""
    if await state.get_state() == BeatFilter.key.state:
        await state.update_data(f_key=None)
        await _ask_bpm(call.message, state, user)
    else:
        await _run_filter(call.message, state, session, user, None, None)
    await call.answer()


async def _run_filter(target: Message, state: FSMContext, session: AsyncSession, user: User,
                      bpm_min: int | None, bpm_max: int | None) -> None:
    data = await state.get_data()
    ids = await repo.filter_beats(
        session, data["category_id"],
        genre=data.get("f_genre"), key=data.get("f_key"),
        bpm_min=bpm_min, bpm_max=bpm_max,
    )
    if not ids:
        await state.set_state(None)
        await target.answer(t("filter_no_results", user.lang))
        return
    await _start_carousel(target, state, session, user, ids)


async def _render_caption(session: AsyncSession, work_id: int, pos: int, total: int, lang: Lang, ctype: str):
    """(работа, подпись) или None, если работу успели удалить."""
    pair = await repo.get_work_with_author(session, work_id)
    if pair is None:
        return None
    work, author = pair
    if ctype == "video":
        caption = t(
            "video_card", lang,
            title=esc(work.title), author=_contact(author),
            vtype=esc(work.genre), buy=fmt_money(work.price_buy),
            pos=pos, total=total,
        )
    elif ctype == "visual":
        caption = t(
            "visual_card", lang,
            title=esc(work.title), author=_contact(author),
            vtype=esc(work.genre), buy=fmt_money(work.price_buy),
            pos=pos, total=total,
        )
    else:
        caption = t(
            "beat_card", lang,
            title=esc(work.title), author=_contact(author),
            genre=esc(work.genre), key=esc(work.key), bpm=work.bpm or "—",
            rent=fmt_money(work.price_rent), buy=fmt_money(work.price_buy),
            pos=pos, total=total,
        )
    return work, caption


def _card_kb(lang: Lang, work: Work, ctype: str):
    return work_card_keyboard(lang, work.id, ctype, has_rent=work.price_rent is not None)


async def _start_carousel(event, state: FSMContext, session: AsyncSession, user: User, ids: list[int]):
    await state.set_state(None)
    data = await state.get_data()
    ctype = data.get("ctype", "beat")
    await state.update_data(beat_ids=ids, beat_idx=0)
    rendered = await _render_caption(session, ids[0], 1, len(ids), user.lang, ctype)
    if rendered is None:
        return
    work, caption = rendered
    target = event.message if isinstance(event, CallbackQuery) else event
    kb = _card_kb(user.lang, work, ctype)
    if ctype == "video":
        await target.answer_video(work.cover_file_id, caption=caption, reply_markup=kb)
    else:
        await target.answer_photo(work.cover_file_id, caption=caption, reply_markup=kb)


@router.callback_query(F.data.in_({"beatnav:prev", "beatnav:next"}))
async def carousel_nav(call: CallbackQuery, state: FSMContext, session: AsyncSession, user: User):
    data = await state.get_data()
    ids = data.get("beat_ids") or []
    if not ids:
        await call.answer(t("button_outdated", user.lang))
        return
    ctype = data.get("ctype", "beat")
    idx = data.get("beat_idx", 0)
    idx = (idx + (1 if call.data.endswith("next") else -1)) % len(ids)
    await state.update_data(beat_idx=idx)
    rendered = await _render_caption(session, ids[idx], idx + 1, len(ids), user.lang, ctype)
    if rendered is None:
        await call.answer(t("button_outdated", user.lang))
        return
    work, caption = rendered
    media_cls = InputMediaVideo if ctype == "video" else InputMediaPhoto
    await call.message.edit_media(
        media_cls(media=work.cover_file_id, caption=caption),
        reply_markup=_card_kb(user.lang, work, ctype),
    )
    await call.answer()


def _can_listen(work: Work, author: User, tg_id: int) -> bool:
    """Одобренную работу слушают все; неопубликованную — только автор и админ
    (callback_data можно подделать и выкачать чужой трек с модерации)."""
    return work.moderation_status == ModerationStatus.approved or tg_id in (app_config.ADMIN_ID, author.tg_id)


@router.callback_query(F.data.startswith("beat:listen:"))
async def beat_listen(call: CallbackQuery, session: AsyncSession, user: User):
    work_id = int(call.data.split(":")[2])
    pair = await repo.get_work_with_author(session, work_id)
    if pair and pair[0].audio_file_id and _can_listen(pair[0], pair[1], call.from_user.id):
        await send_work_audio(call.message, pair[0])
    await call.answer()


@router.callback_query(F.data.startswith("beat:buy:"))
async def beat_buy(call: CallbackQuery, state: FSMContext, session: AsyncSession, user: User, bot: Bot):
    parts = call.data.split(":")
    work_id = int(parts[2])
    kind = parts[3] if len(parts) > 3 else "buy"   # у старых кнопок вида нет
    pair = await repo.get_work_with_author(session, work_id)
    if pair is None or pair[0].moderation_status != ModerationStatus.approved:
        await call.answer(t("button_outdated", user.lang))
        return
    work, author = pair

    # Повторное нажатие не отправляет админу ещё одну такую же заявку.
    data = await state.get_data()
    sent = set(data.get("buy_sent") or [])
    tag = f"{work_id}:{kind}"
    if tag in sent:
        await call.answer(t("beat_buy_already", user.lang), show_alert=True)
        return

    # у битов есть аренда, у визуала/видео — только цена выкупа
    if work.price_rent is None:
        prices = f"Цена: {fmt_money(work.price_buy)} ₽"
    elif kind == "rent":
        prices = f"Хочет: <b>аренду</b> за {fmt_money(work.price_rent)} ₽"
    else:
        prices = f"Хочет: <b>выкуп</b> за {fmt_money(work.price_buy)} ₽"
    text = t(
        "mod_beat_buy", Lang.ru,
        title=esc(work.title), work_id=work.id,
        contact=contact(user), author=contact(author),
        prices=prices,
    )
    await notify_admin(bot, text)
    await state.update_data(buy_sent=sorted(sent | {tag}))
    await call.answer(t("beat_buy_sent", user.lang), show_alert=True)


@router.callback_query(F.data.startswith("beat:ask:"))
async def beat_ask(call: CallbackQuery, state: FSMContext, session: AsyncSession, user: User):
    work_id = int(call.data.split(":")[2])
    pair = await repo.get_work_with_author(session, work_id)
    title = pair[0].title if pair else "—"
    await state.set_state(BeatQuestion.waiting)
    await state.update_data(ask_work_id=work_id, ask_title=title)
    await call.message.answer(t("beat_ask_prompt", user.lang, title=esc(title)), reply_markup=cancel_kb(user.lang))
    await call.answer()


@router.message(BeatQuestion.waiting)
async def beat_ask_send(message: Message, state: FSMContext, user: User, bot: Bot):
    question = await read_text(message, user.lang, QUESTION_MAX)
    if question is None:
        return
    data = await state.get_data()
    text = t(
        "mod_beat_question", Lang.ru,
        title=esc(data.get("ask_title")), work_id=data.get("ask_work_id"),
        # ссылка, а не «id123»: у клиента может не быть @username
        contact=contact(user), text=esc(question),
    )
    await notify_admin(bot, text)
    await state.set_state(None)
    await message.answer(t("beat_ask_sent", user.lang))
