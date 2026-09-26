from aiogram import Bot, F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from sqlalchemy.ext.asyncio import AsyncSession

from bot.categories import DIRECTIONS, direction_by_code
from bot.db.models import Creator, CreatorProfile, CreatorStatus, Lang, Role, User
from bot.db.repositories import profiles as profiles_repo
from bot.db.repositories.works import get_creator
from bot.keyboards.common import (
    lang_keyboard,
    main_menu,
    settings_lang_keyboard,
)
from bot.locales import t
from bot.services.forms import cancel_kb, read_text, step
from bot.services.media import detect_media
from bot.services.moderation import send_profile_card
from bot.services.text import EXPERIENCE_MAX, NICKNAME_MAX, PORTFOLIO_LINKS_MAX, esc
from bot.states.registration import CreatorApplication, Registration

router = Router()

async def _creator_status(session: AsyncSession, user: User) -> CreatorStatus | None:
    return await profiles_repo.menu_status(session, user.id)


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


@router.message(Registration.lang)
async def lang_expected(message: Message):
    """Вместо нажатия кнопки языка прислали текст — показываем выбор ещё раз."""
    await message.answer(t("choose_lang"), reply_markup=lang_keyboard())


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
    nickname = await read_text(message, user.lang, NICKNAME_MAX)
    if nickname is None:
        return
    user.nickname = nickname
    user.role = Role.client  # маркер завершённой регистрации; все — клиенты
    await session.commit()
    await state.clear()
    await message.answer(t("client_registered", user.lang, nickname=esc(user.nickname)))
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


# --- Заявка исполнителя: по одному профилю на направление -----------------

_APP_STEPS = 2


def _directions_kb(free: list, lang: Lang) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=d.title(lang), callback_data=f"appdir:{d.code}")] for d in free
    ])


async def start_creator_application(
    message: Message, state: FSMContext, session: AsyncSession, user: User, username: str | None
):
    """Точка входа по кнопке «Стать исполнителем»: выбор свободного направления.

    username передаётся отдельно: при входе из кабинета message отправлен ботом,
    и message.from_user — это сам бот, а не человек.
    """
    creator = await get_creator(session, user.id)
    if creator is not None and creator.status == CreatorStatus.blocked:
        # раньше тут отвечали «заявка на рассмотрении» — неправда для отклонённых
        await message.answer(t("creator_blocked_info", user.lang),
                             reply_markup=main_menu(user.lang, creator.status))
        return
    if not username:
        await message.answer(t("creator_need_username", user.lang))
        return
    taken = {p.direction for p in await profiles_repo.list_profiles(session, creator.id)} if creator else set()
    free = [d for d in DIRECTIONS if d.code not in taken]
    if not free:
        await message.answer(t("app_all_directions", user.lang))
        return
    await state.clear()
    await message.answer(t("app_choose_direction", user.lang), reply_markup=_directions_kb(free, user.lang))


@router.callback_query(F.data.startswith("appdir:"))
async def app_pick_direction(call: CallbackQuery, state: FSMContext, session: AsyncSession, user: User):
    code = call.data.split(":", 1)[1]
    direction = direction_by_code(code)
    if direction is None:
        await call.answer(t("button_outdated", user.lang))
        return
    creator = await get_creator(session, user.id)
    if creator and await profiles_repo.get_profile_by_direction(session, creator.id, code):
        await call.answer(t("app_direction_taken", user.lang), show_alert=True)
        return
    await state.clear()
    await state.set_state(CreatorApplication.about)
    await state.update_data(direction=code)
    await call.message.answer(
        step(1, _APP_STEPS, "app_ask_about", user.lang, direction=direction.title(user.lang)),
        reply_markup=cancel_kb(user.lang),
    )
    await call.answer()


@router.message(CreatorApplication.about)
async def app_about(message: Message, state: FSMContext, user: User):
    value = await read_text(message, user.lang, EXPERIENCE_MAX)
    if value is None:
        return
    await state.update_data(about=value)
    await state.set_state(CreatorApplication.links)
    await message.answer(step(2, _APP_STEPS, "app_ask_links", user.lang), reply_markup=cancel_kb(user.lang))


def _app_media_kb(lang: Lang) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t("btn_app_media_done", lang), callback_data="appmedia:done")],
        ]
    )


@router.message(CreatorApplication.links)
async def app_links(
    message: Message, state: FSMContext, session: AsyncSession, user: User, bot: Bot
):
    value = await read_text(message, user.lang, PORTFOLIO_LINKS_MAX)
    if value is None:
        return
    data = await state.get_data()
    creator = await get_creator(session, user.id)
    if creator is None:
        # человек-исполнитель заводится один раз; на модерацию идёт профиль направления
        creator = Creator(user_id=user.id, status=CreatorStatus.approved)
        session.add(creator)
        await session.flush()
    profile = CreatorProfile(
        creator_id=creator.id,
        direction=data["direction"],
        status=CreatorStatus.pending,
        about=data.get("about"),
        links=value,
    )
    session.add(profile)
    await session.commit()

    await message.answer(t("creator_application_sent", user.lang))
    await send_profile_card(bot, user, profile)

    # Необязательный цикл: добавить медиа в портфолио этого направления прямо сейчас.
    await state.set_state(CreatorApplication.portfolio_media)
    await state.update_data(creator_id=creator.id, profile_id=profile.id)
    await message.answer(t("app_media_prompt", user.lang), reply_markup=_app_media_kb(user.lang))


@router.message(CreatorApplication.portfolio_media)
async def app_portfolio_media(message: Message, state: FSMContext, session: AsyncSession, user: User):
    from bot.db.repositories import portfolio as pf_repo

    found = detect_media(message)
    if found is None:
        await message.answer(t("need_media", user.lang), reply_markup=_app_media_kb(user.lang))
        return
    data = await state.get_data()
    media_type, file_id = found
    await pf_repo.add_item(session, data["creator_id"], media_type, file_id, None, data.get("profile_id"))
    await message.answer(t("app_media_added", user.lang), reply_markup=_app_media_kb(user.lang))


@router.callback_query(CreatorApplication.portfolio_media, F.data == "appmedia:done")
async def app_finish(call: CallbackQuery, state: FSMContext, session: AsyncSession, user: User):
    await state.clear()
    status = await _creator_status(session, user)
    await call.message.answer(t("main_menu", user.lang), reply_markup=main_menu(user.lang, status))
    await call.answer()
