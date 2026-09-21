from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot import app_config
from bot.categories import by_code
from bot.db.models import Category, Lang, Order, OrderStatus, User
from bot.db.repositories import orders as repo
from bot.db.repositories.works import get_approved_creator, get_category_by_code
from bot.keyboards.orders import take_order_keyboard
from bot.locales import t
from bot.services.forms import cancel_kb, read_text, step_text
from bot.services.media import MAX_ATTACHMENTS, detect_attachment, send_attachments
from bot.services.notify import safe_send
from bot.services.order_view import contact, render_order_card, tender_text
from bot.services.text import BRIEF_FIELD_MAX
from bot.states.orders import OrderForm

router = Router()


# =========================================================================
# ЗАПОЛНЕНИЕ ТЗ (клиент)
# =========================================================================


async def start_order(message: Message, state: FSMContext, session: AsyncSession, user: User, code: str):
    # Заказ доступен любому зарегистрированному пользователю (все — клиенты).
    if user.role is None:
        return
    category = await get_category_by_code(session, code)
    if category is None or not category.thread_id or not app_config.GROUP_ID:
        await message.answer(t("order_category_unavailable", user.lang))
        return

    fields = by_code(code).fields
    await state.clear()
    await state.set_state(OrderForm.filling)
    await state.update_data(code=code, step=0, brief={})
    title = category.title_en if user.lang == Lang.en else category.title_ru
    await message.answer(t("order_form_start", user.lang, title=title))
    await message.answer(
        step_text(1, len(fields), fields[0].prompt(user.lang), user.lang),
        reply_markup=cancel_kb(user.lang),
    )


@router.message(OrderForm.filling)
async def fill_step(message: Message, state: FSMContext, session: AsyncSession, user: User, bot: Bot):
    data = await state.get_data()
    code = data["code"]
    step = data["step"]
    brief = data["brief"]
    fields = by_code(code).fields

    value = await read_text(
        message, user.lang, BRIEF_FIELD_MAX,
        need_key="order_need_text", too_long_key="order_text_too_long",
    )
    if value is None:
        return
    brief[fields[step].key] = value
    step += 1

    if step < len(fields):
        await state.update_data(step=step, brief=brief)
        await message.answer(
            step_text(step + 1, len(fields), fields[step].prompt(user.lang), user.lang),
            reply_markup=cancel_kb(user.lang),
        )
        return

    # Текстовые шаги пройдены — предлагаем необязательно прикрепить изображения/файлы.
    await state.update_data(brief=brief, attachments=[])
    await state.set_state(OrderForm.attachments)
    await message.answer(t("order_attach_prompt", user.lang), reply_markup=_attach_done_kb(user.lang))


def _attach_done_kb(lang: Lang):
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=t("order_attach_done", lang), callback_data="ordattach:done")]]
    )


@router.message(OrderForm.attachments)
async def order_attachment(message: Message, state: FSMContext, user: User):
    # голосовые и кружки тоже годятся — клиенту часто проще надиктовать
    found = detect_attachment(message)
    if found is None:
        await message.answer(t("order_attach_need_media", user.lang), reply_markup=_attach_done_kb(user.lang))
        return
    data = await state.get_data()
    attachments = data.get("attachments", [])
    if len(attachments) >= MAX_ATTACHMENTS:
        await message.answer(
            t("order_attach_limit", user.lang, limit=MAX_ATTACHMENTS), reply_markup=_attach_done_kb(user.lang),
        )
        return
    attachments.append(found)
    await state.update_data(attachments=attachments)
    await message.answer(
        t("order_attach_added", user.lang, count=len(attachments)),
        reply_markup=_attach_done_kb(user.lang),
    )


@router.callback_query(OrderForm.attachments, F.data == "ordattach:done")
async def order_attachments_done(call: CallbackQuery, state: FSMContext, session: AsyncSession, user: User, bot: Bot):
    data = await state.get_data()
    await state.clear()
    code = data["code"]
    brief = data["brief"]
    attachments = data.get("attachments", [])
    if attachments:
        brief["_attachments"] = attachments
    category = await get_category_by_code(session, code)
    order = Order(
        client_id=user.id,
        category_id=category.id,
        brief=brief,
        status=OrderStatus.published,
    )
    session.add(order)
    await session.commit()

    await publish_tender(bot, session, order, category, user)
    await call.message.answer(t("order_published", user.lang, order_id=order.id))
    await call.answer()


async def publish_tender(bot: Bot, session: AsyncSession, order: Order, category: Category, client: User):
    sent = await bot.send_message(
        app_config.GROUP_ID,
        tender_text(order, category, client),
        message_thread_id=category.thread_id,
        reply_markup=take_order_keyboard(Lang.ru, order.id),
    )
    order.tender_message_id = sent.message_id
    await session.commit()

    # Вложения — альбомами и ответом на пост-тендер: в топике с несколькими
    # заказами они больше не перемешиваются с чужими.
    attachments = (order.brief or {}).get("_attachments") or []
    if attachments:
        await send_attachments(
            bot, app_config.GROUP_ID, attachments,
            thread_id=category.thread_id, reply_to=sent.message_id,
        )


# =========================================================================
# ВЗЯТЬ ЗАКАЗ (исполнитель, в топике категории)
# =========================================================================


@router.callback_query(F.data.startswith("ordtake:"))
async def take_order(call: CallbackQuery, session: AsyncSession, user: User | None, bot: Bot):
    order_id = int(call.data.split(":")[1])
    if user is None:
        # участник группы, ни разу не запускавший бота: раньше кнопка молча не работала
        await call.answer(t("order_take_need_start", Lang.ru), show_alert=True)
        return
    creator = await get_approved_creator(session, user.id)
    if creator is None:
        await call.answer(t("order_take_only_creator", user.lang), show_alert=True)
        return

    ok = await repo.claim_order(session, order_id, creator.id)
    if not ok:
        await call.answer(t("order_already_taken", user.lang), show_alert=True)
        return

    # помечаем тендер как взятый
    try:
        await call.message.edit_text(
            call.message.html_text + t("tender_taken_mark", Lang.ru, contact=contact(user))
        )
    except Exception:
        pass

    # клиенту — карточка заказа с кнопкой утверждения исполнителя
    bundle = await repo.get_full(session, order_id)
    order, client, category, creator_user = bundle
    text, kb = render_order_card(order, client, category, creator_user, "client", client.lang)
    await safe_send(bot.send_message(client.tg_id, text, reply_markup=kb))
    # исполнителю — карточка в личку: всплывашка в группе исчезает через пару секунд
    text, kb = render_order_card(order, client, category, creator_user, "creator", user.lang)
    await safe_send(bot.send_message(user.tg_id, text, reply_markup=kb))

    await call.answer(t("order_taken_ok", user.lang, order_id=order_id))
