from decimal import Decimal, InvalidOperation

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import get_settings
from bot.db.models import (
    Category,
    Creator,
    Lang,
    Order,
    OrderStatus,
    Role,
    User,
)
from bot.categories import by_code
from bot.db.repositories import orders as repo
from bot.db.repositories.works import get_category_by_code, get_approved_creator
from bot.keyboards.orders import (
    admin_final_keyboard,
    admin_prepay_keyboard,
    client_cancel_keyboard,
    client_confirm_keyboard,
    take_order_keyboard,
)
from bot.locales import t
from bot.services.notify import notify_admin, send_to_moderation
from bot.states.orders import AdminPayout, OrderForm

router = Router()
settings = get_settings()


def _contact(user: User) -> str:
    if user.username:
        return f"@{user.username}"
    return f'<a href="tg://user?id={user.tg_id}">{user.nickname or "профиль"}</a>'


async def _creator_user(session: AsyncSession, creator_id: int) -> tuple[Creator, User] | None:
    res = await session.execute(
        select(Creator, User).join(User, User.id == Creator.user_id).where(Creator.id == creator_id)
    )
    row = res.first()
    return (row[0], row[1]) if row else None


async def _order_bundle(session: AsyncSession, order_id: int):
    """Возвращает (order, client, category)."""
    order = await session.get(Order, order_id)
    if order is None:
        return None
    client = await session.get(User, order.client_id)
    category = await session.get(Category, order.category_id)
    return order, client, category


# =========================================================================
# ЗАПОЛНЕНИЕ ТЗ (клиент)
# =========================================================================


async def start_order(message: Message, state: FSMContext, session: AsyncSession, user: User, code: str):
    if user.role != Role.client:
        await message.answer(t("order_only_client", user.lang))
        return
    category = await get_category_by_code(session, code)
    if category is None or not category.thread_id or not settings.group_id:
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

    # форма заполнена — создаём заказ и публикуем тендер
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

    await _publish_tender(bot, session, order, category, user)
    await message.answer(t("order_published", user.lang, order_id=order.id))


async def _publish_tender(bot: Bot, session: AsyncSession, order: Order, category: Category, client: User):
    fields = by_code(category.code).fields
    body = "\n".join(f"• {f.label}: {order.brief.get(f.key, '—')}" for f in fields)
    text = t(
        "tender_card", Lang.ru,
        title=category.title_ru, order_id=order.id,
        contact=_contact(client), body=body,
    )
    sent = await bot.send_message(
        settings.group_id,
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

    bundle = await _order_bundle(session, order_id)
    order, client, category = bundle

    # отмечаем тендер как взятый
    try:
        await call.message.edit_text(
            call.message.html_text + t("tender_taken_mark", Lang.ru, contact=_contact(user))
        )
    except Exception:
        pass

    # уведомляем клиента — просим утвердить исполнителя
    await bot.send_message(
        client.tg_id,
        t("client_creator_took", client.lang, contact=_contact(user), order_id=order_id),
        reply_markup=client_confirm_keyboard(client.lang, order_id),
    )
    await call.answer(t("order_taken_ok", user.lang, order_id=order_id))


# =========================================================================
# КЛИЕНТ: утвердить / отменить
# =========================================================================


@router.callback_query(F.data.startswith("ordclient:confirm:"))
async def client_confirm(call: CallbackQuery, session: AsyncSession, user: User, bot: Bot):
    order_id = int(call.data.split(":")[2])
    order, client, category = await _order_bundle(session, order_id)
    if order.status != OrderStatus.taken:
        await call.answer()
        return
    await repo.set_status(session, order_id, OrderStatus.await_prepay)

    # инструкции по оплате клиенту
    await call.message.edit_text(
        t("client_pay_instructions", user.lang, order_id=order_id, details=settings.payment_details)
    )

    # карточка админу с кнопкой подтверждения предоплаты
    cu = await _creator_user(session, order.creator_id)
    creator_contact = _contact(cu[1]) if cu else "—"
    await notify_admin(
        bot,
        t("admin_await_prepay", Lang.ru, order_id=order_id, title=category.title_ru,
          client=_contact(client), creator=creator_contact),
        admin_prepay_keyboard(order_id),
    )
    await call.answer()


@router.callback_query(F.data.startswith("ordclient:cancel:"))
async def client_cancel(call: CallbackQuery, session: AsyncSession, user: User, bot: Bot):
    order_id = int(call.data.split(":")[2])
    order, client, category = await _order_bundle(session, order_id)
    if order.status in (OrderStatus.completed, OrderStatus.cancelled):
        await call.answer()
        return
    # арбитраж: возвращаем на модерацию (снимаем исполнителя)
    order.status = OrderStatus.cancelled
    order.creator_id = None
    await session.commit()

    await call.message.edit_text(t("order_cancelled_client", user.lang, order_id=order_id))
    await send_to_moderation(bot, t("admin_order_cancelled", Lang.ru, order_id=order_id))
    await call.answer()


# =========================================================================
# АДМИН: предоплата и финал
# =========================================================================


@router.callback_query(F.data.startswith("ordadmin:prepay:"))
async def admin_prepay(call: CallbackQuery, session: AsyncSession, bot: Bot):
    if call.from_user.id != settings.admin_id:
        await call.answer()
        return
    order_id = int(call.data.split(":")[2])
    order, client, category = await _order_bundle(session, order_id)
    await repo.set_status(session, order_id, OrderStatus.in_progress)

    cu = await _creator_user(session, order.creator_id)
    if cu:
        creator, creator_user = cu
        # обмен контактами
        await bot.send_message(
            creator_user.tg_id,
            t("contacts_to_creator", creator_user.lang, order_id=order_id, contact=_contact(client)),
        )
        await bot.send_message(
            client.tg_id,
            t("contacts_to_client", client.lang, order_id=order_id, contact=_contact(creator_user)),
            reply_markup=client_cancel_keyboard(client.lang, order_id),
        )

    await call.message.edit_text(call.message.html_text + f"\n\n✅ {t('admin_prepay_done', Lang.ru)}")
    # следующая кнопка — подтверждение финальной оплаты
    await notify_admin(
        bot,
        t("admin_await_prepay", Lang.ru, order_id=order_id, title=category.title_ru,
          client=_contact(client), creator=_contact(cu[1]) if cu else "—"),
        admin_final_keyboard(order_id),
    )
    await call.answer(t("admin_prepay_done", Lang.ru))


@router.callback_query(F.data.startswith("ordadmin:final:"))
async def admin_final(call: CallbackQuery, state: FSMContext, bot: Bot):
    if call.from_user.id != settings.admin_id:
        await call.answer()
        return
    order_id = int(call.data.split(":")[2])
    await state.set_state(AdminPayout.amount)
    await state.update_data(order_id=order_id)
    await call.message.answer(t("admin_enter_payout", Lang.ru, order_id=order_id))
    await call.answer()


@router.message(AdminPayout.amount)
async def admin_payout(message: Message, state: FSMContext, session: AsyncSession, bot: Bot):
    if message.from_user.id != settings.admin_id:
        return
    raw = (message.text or "").strip().replace(",", ".").replace(" ", "")
    try:
        amount = Decimal(raw)
    except InvalidOperation:
        await message.answer(t("admin_payout_invalid", Lang.ru))
        return

    data = await state.get_data()
    order_id = data["order_id"]
    await state.clear()

    order, client, category = await _order_bundle(session, order_id)
    order.status = OrderStatus.completed
    cu = await _creator_user(session, order.creator_id)
    if cu:
        creator, creator_user = cu
        creator.balance = (creator.balance or Decimal(0)) + amount
        await session.commit()
        await bot.send_message(
            creator_user.tg_id,
            t("creator_balance_credited", creator_user.lang, order_id=order_id, amount=amount),
        )
    else:
        await session.commit()

    await bot.send_message(client.tg_id, t("client_order_completed", client.lang, order_id=order_id))
    await message.answer(t("admin_final_done", Lang.ru, order_id=order_id, amount=amount))
