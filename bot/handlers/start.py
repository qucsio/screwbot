from aiogram import Bot, F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import Creator, CreatorStatus, Lang, Role, User
from bot.keyboards.common import (
    lang_keyboard,
    main_menu,
    moderation_keyboard,
    role_keyboard,
)
from bot.locales import t
from bot.services.notify import send_to_moderation
from bot.states.registration import CreatorApplication, Registration

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, user: User | None):
    await state.clear()
    # Уже зарегистрирован — сразу меню
    if user and user.role:
        await message.answer(t("main_menu", user.lang), reply_markup=main_menu(user.lang))
        return
    await state.set_state(Registration.lang)
    await message.answer(t("choose_lang"), reply_markup=lang_keyboard())


@router.callback_query(Registration.lang, F.data.startswith("lang:"))
async def choose_lang(call: CallbackQuery, state: FSMContext, session: AsyncSession):
    lang = Lang(call.data.split(":")[1])
    # upsert пользователя с языком
    tg = call.from_user
    user = User(
        tg_id=tg.id,
        username=tg.username,
        lang=lang,
    )
    session.add(user)
    await session.commit()

    await state.update_data(lang=lang.value)
    await state.set_state(Registration.role)
    await call.message.edit_text(t("lang_set", lang))
    await call.message.answer(t("choose_role", lang), reply_markup=role_keyboard(lang))
    await call.answer()


@router.callback_query(Registration.role, F.data.startswith("role:"))
async def choose_role(
    call: CallbackQuery, state: FSMContext, session: AsyncSession, user: User
):
    lang = user.lang
    role = call.data.split(":")[1]

    if not call.from_user.username:
        await call.message.answer(t("no_username", lang))
        await call.answer()
        return

    if role == "client":
        user.role = Role.client
        await state.set_state(Registration.nickname)
        await call.message.edit_text(t("ask_nickname", lang))
    else:
        user.role = Role.creator
        await state.set_state(CreatorApplication.service)
        await call.message.edit_text(t("creator_ask_service", lang))
    await session.commit()
    await call.answer()


@router.message(Registration.nickname)
async def set_nickname(message: Message, state: FSMContext, session: AsyncSession, user: User):
    user.nickname = message.text.strip()[:64]
    await session.commit()
    await state.clear()
    await message.answer(
        t("client_registered", user.lang, nickname=user.nickname),
        reply_markup=main_menu(user.lang),
    )


# --- Заявка исполнителя --------------------------------------------------


@router.message(CreatorApplication.service)
async def app_service(message: Message, state: FSMContext, user: User):
    await state.update_data(service=message.text.strip()[:128])
    await state.set_state(CreatorApplication.experience)
    await message.answer(t("creator_ask_experience", user.lang))


@router.message(CreatorApplication.experience)
async def app_experience(message: Message, state: FSMContext, user: User):
    await state.update_data(experience=message.text.strip())
    await state.set_state(CreatorApplication.portfolio)
    await message.answer(t("creator_ask_portfolio", user.lang))


@router.message(CreatorApplication.portfolio)
async def app_portfolio(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    user: User,
    bot: Bot,
):
    data = await state.get_data()
    creator = Creator(
        user_id=user.id,
        status=CreatorStatus.pending,
        service=data.get("service"),
        experience=data.get("experience"),
        portfolio=message.text.strip(),
    )
    session.add(creator)
    await session.commit()
    await state.clear()

    await message.answer(t("creator_application_sent", user.lang))

    # Карточка в чат модерации (с кликабельным контактом)
    contact = f"@{user.username}" if user.username else f"id{user.tg_id}"
    card = t(
        "mod_new_creator",
        Lang.ru,
        contact=contact,
        nickname=user.nickname or "—",
        service=creator.service or "—",
        experience=creator.experience or "—",
        portfolio=creator.portfolio or "—",
    )
    await send_to_moderation(bot, card, moderation_keyboard(Lang.ru, creator.id))
