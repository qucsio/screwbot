from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    Message,
)
from sqlalchemy.ext.asyncio import AsyncSession

from bot import app_config
from bot.db.models import Lang, User
from bot.db.repositories import reviews as repo
from bot.db.repositories.works import get_approved_creator
from bot.keyboards.common import creator_panel
from bot.locales import t
from bot.services.forms import cancel_kb
from bot.states.reviews import ReviewUpload

router = Router()


def _carousel_keyboard(lang: Lang) -> InlineKeyboardMarkup:
    rows = [[
        InlineKeyboardButton(text=t("review_prev", lang), callback_data="revnav:prev"),
        InlineKeyboardButton(text=t("review_next", lang), callback_data="revnav:next"),
    ]]
    if app_config.REVIEWS_CHANNEL_URL:
        rows.append([InlineKeyboardButton(text=t("btn_reviews_channel", lang), url=app_config.REVIEWS_CHANNEL_URL)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# =========================================================================
# ЗАГРУЗКА ОТЗЫВА (исполнитель)
# =========================================================================


async def start_review_upload(message: Message, state: FSMContext, session: AsyncSession, user: User):
    creator = await get_approved_creator(session, user.id)
    if creator is None:
        await message.answer(t("review_only_creator", user.lang))
        return
    await state.clear()
    await state.set_state(ReviewUpload.photo)
    await message.answer(t("review_ask_photo", user.lang), reply_markup=cancel_kb(user.lang))


@router.message(Command("review"))
async def review_start(message: Message, state: FSMContext, session: AsyncSession, user: User | None):
    if user is None:
        return
    await start_review_upload(message, state, session, user)


@router.message(ReviewUpload.photo, F.photo)
async def review_photo(message: Message, state: FSMContext, session: AsyncSession, user: User, bot: Bot):
    creator = await get_approved_creator(session, user.id)
    if creator is None:
        await state.clear()
        return
    file_id = message.photo[-1].file_id
    await repo.add_review(session, creator.id, file_id)
    await state.clear()

    # зеркалим в публичный канал
    saved_key = "review_saved_no_channel"
    if app_config.REVIEWS_CHANNEL_ID:
        try:
            await bot.send_photo(app_config.REVIEWS_CHANNEL_ID, file_id)
            saved_key = "review_saved"
        except Exception:
            pass
    await message.answer(t(saved_key, user.lang), reply_markup=creator_panel(user.lang))


@router.message(ReviewUpload.photo)
async def review_not_photo(message: Message, user: User):
    await message.answer(t("review_not_photo", user.lang), reply_markup=cancel_kb(user.lang))


# =========================================================================
# ПРОСМОТР ОТЗЫВОВ (клиент) — вкладка меню
# =========================================================================


async def open_reviews(message: Message, state: FSMContext, session: AsyncSession, user: User):
    photos = await repo.last_reviews(session, limit=10)
    if not photos:
        await message.answer(t("reviews_empty", user.lang, url=app_config.REVIEWS_CHANNEL_URL or "—"))
        return
    await state.clear()
    await state.update_data(rev_ids=photos, rev_idx=0)
    await message.answer(t("reviews_intro", user.lang, url=app_config.REVIEWS_CHANNEL_URL or "—"))
    await message.answer_photo(
        photos[0],
        caption=t("review_card", user.lang, pos=1, total=len(photos)),
        reply_markup=_carousel_keyboard(user.lang),
    )


@router.callback_query(F.data.in_({"revnav:prev", "revnav:next"}))
async def review_nav(call: CallbackQuery, state: FSMContext, user: User):
    data = await state.get_data()
    photos = data.get("rev_ids") or []
    if not photos:
        await call.answer()
        return
    idx = data.get("rev_idx", 0)
    idx = (idx + (1 if call.data.endswith("next") else -1)) % len(photos)
    await state.update_data(rev_idx=idx)
    await call.message.edit_media(
        InputMediaPhoto(
            media=photos[idx],
            caption=t("review_card", user.lang, pos=idx + 1, total=len(photos)),
        ),
        reply_markup=_carousel_keyboard(user.lang),
    )
    await call.answer()
