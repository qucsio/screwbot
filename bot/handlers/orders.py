from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot import app_config
from bot.categories import by_code
from bot.db.models import Category, Lang, Order, OrderStatus, Role, User
from bot.db.repositories import orders as repo
from bot.db.repositories.works import get_approved_creator, get_category_by_code
from bot.keyboards.orders import take_order_keyboard
from bot.locales import t
from bot.services.order_view import contact, render_order_card
from bot.states.orders import OrderForm

router = Router()


# =========================================================================
# ЗАПОЛНЕНИЕ ТЗ (клиент)
# =========================================================================


async def start_order(message: Message, state: FSMContext, session: AsyncSession, user: User, code: str):
    if user.role != Role.client:
        await message.answer(t("order_only_client", user.lang))
        return
    category = await get_category_by_code(session, code)
    if category is None or not category.thread_id or not app_config.GROUP_ID:
        await message.answer(t("order_category_unavailable", user.lang))
        return

    await state.clear()
    await state.set_state(OrderForm.filling)
    await state.update_data(code=code, step=0, brief={})
    title = category.title_en if user.lang == Lang.en else category.title_ru
    await message.answer(t("order_form_start", user.lang, title=title))
    await message.answer(by_code(code).fields[0].prompt(user.lang))


@router.message(OrderForm.filling, Command("cancel"))
async def cancel_form(message: Message, state: FSMContext, user: User):
    await state.clear()
    await message.answer(t("order_form_cancelled", user.lang))


@router.message(OrderForm.filling)
async def fill_step(message: Message, state: FSMContext, session: AsyncSession, user: User, bot: Bot):
    data = await state.get_data()
    code = data["code"]
    step = data["step"]
    brief = data["brief"]
    fields = by_code(code).fields

    brief[fields[step].key] = (message.text or "").strip()
    step += 1

    if step < len(fields):
        await state.update_data(step=step, brief=brief)
        await message.answer(fields[step].prompt(user.lang))
        return

    await state.clear()
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
    await message.answer(t("order_published", user.lang, order_id=order.id))


async def publish_tender(bot: Bot, session: AsyncSession, order: Order, category: Category, client: User):
    fields = by_code(category.code).fields
    body = "\n".join(f"• {f.label}: {order.brief.get(f.key, '—')}" for f in fields)
    text = t(
        "tender_card", Lang.ru,
        title=category.title_ru, order_id=order.id,
        contact=contact(client), body=body,
    )
    sent = await bot.send_message(
        app_config.GROUP_ID,
        text,
        message_thread_id=category.thread_id,
        reply_markup=take_order_keyboard(Lang.ru, order.id),
    )
    order.tender_message_id = sent.message_id
    await session.commit()


# =========================================================================
# ВЗЯТЬ ЗАКАЗ (исполнитель, в топике категории)
# =========================================================================


@router.callback_query(F.data.startswith("ordtake:"))
async def take_order(call: CallbackQuery, session: AsyncSession, user: User | None, bot: Bot):
    order_id = int(call.data.split(":")[1])
    if user is None:
        await call.answer()
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
    await bot.send_message(client.tg_id, text, reply_markup=kb)

    await call.answer(t("order_taken_ok", user.lang, order_id=order_id))
