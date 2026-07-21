from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import Creator, CreatorStatus, Lang, Role, User
from bot.db.repositories.works import get_creator
from bot.keyboards.common import (
    lang_keyboard,
    main_menu,
    moderation_keyboard,
    settings_lang_keyboard,
)
from bot.locales import t
from bot.services.forms import cancel_kb, guard_text, step
from bot.services.notify import send_to_moderation
from bot.states.registration import CreatorApplication, Registration

router = Router()

_APP_STEPS = 3


async def _creator_status(session: AsyncSession, user: User) -> CreatorStatus | None:
    creator = await get_creator(session, user.id)
    return creator.status if creator else None


async def _menu(message: Message, session: AsyncSession, user: User) -> None:
    status = await _creator_status(session, user)
    await message.answer(t("main_menu", user.lang), reply_markup=main_menu(user.lang, status))


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, session: AsyncSession, user: User | None):
    await state.clear()
    # Уже зарегистрирован — сразу меню
    if user and user.role:
        await _menu(message, session, user)
        return
    await state.set_state(Registration.lang)
    await message.answer(t("choose_lang"), reply_markup=lang_keyboard())


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext, session: AsyncSession, user: User | None):
    """Универсальная отмена любого пошагового процесса."""
    await state.clear()
    if user and user.role:
        status = await _creator_status(session, user)
        await message.answer(t("cancelled", user.lang), reply_markup=main_menu(user.lang, status))
    else:
        await message.answer(t("cancelled", user.lang if user else Lang.ru))


@router.callback_query(Registration.lang, F.data.startswith("lang:"))
async def choose_lang(
    call: CallbackQuery, state: FSMContext, session: AsyncSession, user: User | None
):
    lang = Lang(call.data.split(":")[1])
    # upsert: не плодим дубли при повторной регистрации
    tg = call.from_user
    if user is None:
        user = User(tg_id=tg.id, username=tg.username, lang=lang)
        session.add(user)
    else:
        user.username = tg.username
        user.lang = lang
    await session.commit()

    await state.set_state(Registration.nickname)
    await call.message.edit_text(t("lang_set", lang))
    await call.message.answer(t("ask_nickname", lang), reply_markup=cancel_kb(lang))
    await call.answer()


@router.message(Registration.nickname)
async def set_nickname(message: Message, state: FSMContext, session: AsyncSession, user: User):
    nickname = guard_text(message)
    if nickname is None:
        await message.answer(t("need_text", user.lang), reply_markup=cancel_kb(user.lang))
        return
    user.nickname = nickname[:64]
    user.role = Role.client  # маркер завершённой регистрации; все — клиенты
    await session.commit()
    await state.clear()
    await message.answer(t("client_registered", user.lang, nickname=user.nickname))
    await _menu(message, session, user)


# --- Смена языка после регистрации --------------------------------------


async def open_settings(message: Message, user: User) -> None:
    await message.answer(t("settings_choose_lang", user.lang), reply_markup=settings_lang_keyboard())


@router.callback_query(F.data.startswith("setlang:"))
async def change_lang(call: CallbackQuery, session: AsyncSession, user: User | None):
    if user is None:
        await call.answer()
        return
    user.lang = Lang(call.data.split(":")[1])
    await session.commit()
    await call.message.edit_text(t("settings_lang_saved", user.lang))
    status = await _creator_status(session, user)
    await call.message.answer(t("main_menu", user.lang), reply_markup=main_menu(user.lang, status))
    await call.answer()


# --- Заявка исполнителя (из меню) ----------------------------------------


async def start_creator_application(
    message: Message, state: FSMContext, session: AsyncSession, user: User
):
    """Точка входа по кнопке «Стать исполнителем»."""
    creator = await get_creator(session, user.id)
    if creator is not None:
        if creator.status == CreatorStatus.approved:
            await message.answer(t("creator_already_approved", user.lang))
        else:
            await message.answer(t("application_pending_info", user.lang))
        return
    if not message.from_user.username:
        await message.answer(t("creator_need_username", user.lang))
        return
    await state.clear()
    await state.set_state(CreatorApplication.service)
    await message.answer(t("become_creator_intro", user.lang))
    await message.answer(step(1, _APP_STEPS, "creator_ask_service", user.lang), reply_markup=cancel_kb(user.lang))


@router.message(CreatorApplication.service)
async def app_service(message: Message, state: FSMContext, user: User):
    value = guard_text(message)
    if value is None:
        await message.answer(t("need_text", user.lang), reply_markup=cancel_kb(user.lang))
        return
    await state.update_data(service=value[:128])
    await state.set_state(CreatorApplication.experience)
    await message.answer(step(2, _APP_STEPS, "creator_ask_experience", user.lang), reply_markup=cancel_kb(user.lang))


@router.message(CreatorApplication.experience)
async def app_experience(message: Message, state: FSMContext, user: User):
    value = guard_text(message)
    if value is None:
        await message.answer(t("need_text", user.lang), reply_markup=cancel_kb(user.lang))
        return
    await state.update_data(experience=value)
    await state.set_state(CreatorApplication.portfolio)
    await message.answer(step(3, _APP_STEPS, "creator_ask_portfolio", user.lang), reply_markup=cancel_kb(user.lang))


def _app_media_kb(lang: Lang) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t("btn_app_media_done", lang), callback_data="appmedia:done")],
        ]
    )


async def _send_mod_card(bot: Bot, user: User, creator: Creator) -> None:
    contact = f"@{user.username}" if user.username else f"id{user.tg_id}"
    card = t(
        "mod_new_creator", Lang.ru,
        contact=contact,
        nickname=user.nickname or "—",
        service=creator.service or "—",
        experience=creator.experience or "—",
        portfolio=creator.portfolio or "—",
    )
    await send_to_moderation(bot, card, moderation_keyboard(Lang.ru, creator.id))


@router.message(CreatorApplication.portfolio)
async def app_portfolio(
    message: Message, state: FSMContext, session: AsyncSession, user: User, bot: Bot
):
    value = guard_text(message)
    if value is None:
        await message.answer(t("need_text", user.lang), reply_markup=cancel_kb(user.lang))
        return
    data = await state.get_data()
    creator = Creator(
        user_id=user.id,
        status=CreatorStatus.pending,
        service=data.get("service"),
        experience=data.get("experience"),
        portfolio=value,
    )
    session.add(creator)
    await session.commit()

    # Заявка уже валидна — сразу шлём карточку админу (медиа он видит по кнопке «live»).
    await message.answer(t("creator_application_sent", user.lang))
    await _send_mod_card(bot, user, creator)

    # Необязательный цикл: добавить медиа в портфолио прямо сейчас.
    await state.set_state(CreatorApplication.portfolio_media)
    await state.update_data(creator_id=creator.id)
    await message.answer(t("app_media_prompt", user.lang), reply_markup=_app_media_kb(user.lang))


@router.message(CreatorApplication.portfolio_media)
async def app_portfolio_media(message: Message, state: FSMContext, session: AsyncSession, user: User):
    from bot.db.repositories import portfolio as pf_repo
    from bot.handlers.portfolio import detect_media

    found = detect_media(message)
    if found is None:
        await message.answer(t("need_media", user.lang), reply_markup=_app_media_kb(user.lang))
        return
    data = await state.get_data()
    media_type, file_id = found
    await pf_repo.add_item(session, data["creator_id"], media_type, file_id, None)
    await message.answer(t("app_media_added", user.lang), reply_markup=_app_media_kb(user.lang))


@router.callback_query(CreatorApplication.portfolio_media, F.data == "appmedia:done")
async def app_finish(call: CallbackQuery, state: FSMContext, session: AsyncSession, user: User):
    await state.clear()
    status = await _creator_status(session, user)
    await call.message.answer(t("main_menu", user.lang), reply_markup=main_menu(user.lang, status))
    await call.answer()
