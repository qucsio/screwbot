from decimal import Decimal, InvalidOperation

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from sqlalchemy.ext.asyncio import AsyncSession

from bot import app_config
from bot.db.models import Lang, OrderStatus, User
from bot.db.repositories import orders as repo
from bot.db.repositories.works import get_approved_creator
from bot.locales import t
from bot.services.notify import notify_admin, send_to_moderation
from bot.services.order_view import contact, render_order_card
from bot.states.orders import AdminPayout

router = Router()


# =========================================================================
# ХАБ «МОИ ЗАКАЗЫ»
# =========================================================================


def _list_keyboard(orders, lang: Lang) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(
            text=f"#{o.id} · {t(f'ostatus_{o.status.value}', lang)}",
            callback_data=f"ord:open:{o.id}",
        )]
        for o in orders
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _load_orders(session: AsyncSession, user: User, as_creator: bool):
    if as_creator:
        creator = await get_approved_creator(session, user.id)
        orders = await repo.list_for_creator(session, creator.id) if creator else []
        return orders, "hub_orders_creator"
    orders = await repo.list_for_client(session, user.id)
    return orders, "hub_orders_client"


async def open_orders(
    message: Message, state: FSMContext, session: AsyncSession, user: User, as_creator: bool = False
):
    """Вход из меню: клиентские «Мои заказы» или исполнительские «Заказы в работе»."""
    await state.update_data(orders_scope="creator" if as_creator else "client")
    orders, title_key = await _load_orders(session, user, as_creator)
    if not orders:
        await message.answer(t("hub_orders_empty", user.lang))
        return
    await message.answer(t(title_key, user.lang), reply_markup=_list_keyboard(orders, user.lang))


def _viewer_for_order(user: User, order, creator_user) -> str:
    """Роль-наблюдатель определяется по конкретному заказу (юзер может быть и тем, и тем)."""
    if creator_user and creator_user[1].id == user.id:
        return "creator"
    return "client"


def _with_back(kb: InlineKeyboardMarkup | None, lang: Lang) -> InlineKeyboardMarkup:
    rows = list(kb.inline_keyboard) if kb else []
    rows.append([InlineKeyboardButton(text=t("btn_orders_back", lang), callback_data="ord:list")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data == "ord:list")
async def back_to_list(call: CallbackQuery, state: FSMContext, session: AsyncSession, user: User):
    data = await state.get_data()
    as_creator = data.get("orders_scope") == "creator"
    orders, title_key = await _load_orders(session, user, as_creator)
    if not orders:
        await call.message.edit_text(t("hub_orders_empty", user.lang))
    else:
        await call.message.edit_text(t(title_key, user.lang), reply_markup=_list_keyboard(orders, user.lang))
    await call.answer()


@router.callback_query(F.data.startswith("ord:open:"))
async def open_card(call: CallbackQuery, session: AsyncSession, user: User):
    order_id = int(call.data.split(":")[2])
    bundle = await repo.get_full(session, order_id)
    if bundle is None:
        await call.answer()
        return
    order, client, category, creator_user = bundle
    viewer = _viewer_for_order(user, order, creator_user)
    text, kb = render_order_card(order, client, category, creator_user, viewer, user.lang)
    await call.message.edit_text(text, reply_markup=_with_back(kb, user.lang))
    await call.answer()


# =========================================================================
# ХЕЛПЕРЫ ОТПРАВКИ КАРТОЧЕК
# =========================================================================


async def _push_card(bot: Bot, tg_id: int, bundle, viewer: str, lang: Lang):
    order, client, category, creator_user = bundle
    text, kb = render_order_card(order, client, category, creator_user, viewer, lang)
    await bot.send_message(tg_id, text, reply_markup=kb)


async def _refresh(call: CallbackQuery, bundle, viewer: str, lang: Lang, with_back: bool = True):
    order, client, category, creator_user = bundle
    text, kb = render_order_card(order, client, category, creator_user, viewer, lang)
    markup = _with_back(kb, lang) if with_back else kb
    try:
        await call.message.edit_text(text, reply_markup=markup)
    except Exception:
        pass


# =========================================================================
# ПЕРЕХОДЫ СОСТОЯНИЙ
# =========================================================================


@router.callback_query(F.data.startswith("ord:confirmcreator:"))
async def confirm_creator(call: CallbackQuery, session: AsyncSession, user: User, bot: Bot):
    order_id = int(call.data.split(":")[2])
    bundle = await repo.get_full(session, order_id)
    order, client, category, creator_user = bundle
    if order.status != OrderStatus.taken or order.client_id != user.id:
        await call.answer()
        return
    await repo.set_status(session, order_id, OrderStatus.await_prepay)
    bundle = await repo.get_full(session, order_id)

    await _refresh(call, bundle, "client", user.lang)
    if creator_user:
        await bot.send_message(creator_user[1].tg_id,
                               t("notify_creator_confirmed", creator_user[1].lang, order_id=order_id))
    await _push_card(bot, app_config.ADMIN_ID, bundle, "admin", Lang.ru)
    await call.answer()


@router.callback_query(F.data.startswith("ord:prepay:"))
async def admin_prepay(call: CallbackQuery, session: AsyncSession, bot: Bot):
    if call.from_user.id != app_config.ADMIN_ID:
        await call.answer()
        return
    order_id = int(call.data.split(":")[2])
    bundle = await repo.get_full(session, order_id)
    order, client, category, creator_user = bundle
    if order.status != OrderStatus.await_prepay:
        await call.answer()
        return
    await repo.set_status(session, order_id, OrderStatus.in_progress)
    bundle = await repo.get_full(session, order_id)

    await _refresh(call, bundle, "admin", Lang.ru, with_back=False)
    await _push_card(bot, client.tg_id, bundle, "client", client.lang)
    if creator_user:
        await _push_card(bot, creator_user[1].tg_id, bundle, "creator", creator_user[1].lang)
    await call.answer()


@router.callback_query(F.data.startswith("ord:demodone:"))
async def demo_done(call: CallbackQuery, session: AsyncSession, user: User, bot: Bot):
    order_id = int(call.data.split(":")[2])
    bundle = await repo.get_full(session, order_id)
    order, client, category, creator_user = bundle
    if order.status != OrderStatus.in_progress or not creator_user or creator_user[1].id != user.id:
        await call.answer()
        return
    await repo.set_status(session, order_id, OrderStatus.demo_review)
    bundle = await repo.get_full(session, order_id)

    await _refresh(call, bundle, "creator", user.lang)
    await bot.send_message(client.tg_id, t("notify_demo_to_client", client.lang, order_id=order_id))
    await _push_card(bot, client.tg_id, bundle, "client", client.lang)
    await call.answer()


@router.callback_query(F.data.startswith("ord:approvedemo:"))
async def approve_demo(call: CallbackQuery, session: AsyncSession, user: User, bot: Bot):
    order_id = int(call.data.split(":")[2])
    bundle = await repo.get_full(session, order_id)
    order, client, category, creator_user = bundle
    if order.status != OrderStatus.demo_review or order.client_id != user.id:
        await call.answer()
        return
    await repo.set_status(session, order_id, OrderStatus.await_final)
    bundle = await repo.get_full(session, order_id)

    await _refresh(call, bundle, "client", user.lang)
    if creator_user:
        await bot.send_message(creator_user[1].tg_id,
                               t("notify_demo_approved_creator", creator_user[1].lang, order_id=order_id))
    await call.answer()


@router.callback_query(F.data.startswith("ord:paid:"))
async def client_paid(call: CallbackQuery, session: AsyncSession, user: User, bot: Bot):
    order_id = int(call.data.split(":")[2])
    bundle = await repo.get_full(session, order_id)
    order, client, category, creator_user = bundle
    if order.status != OrderStatus.await_final or order.client_id != user.id:
        await call.answer()
        return
    await _push_card(bot, app_config.ADMIN_ID, bundle, "admin", Lang.ru)
    await bot.send_message(app_config.ADMIN_ID, t("notify_paid_admin", Lang.ru, order_id=order_id))
    # Убираем кнопку, чтобы клиент не слал повторные пинги админу.
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await call.answer(t("order_paid_waiting", user.lang), show_alert=True)


@router.callback_query(F.data.startswith("ord:final:"))
async def admin_final(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != app_config.ADMIN_ID:
        await call.answer()
        return
    order_id = int(call.data.split(":")[2])
    await state.set_state(AdminPayout.amount)
    await state.update_data(order_id=order_id)
    await call.message.answer(t("admin_enter_payout", Lang.ru, order_id=order_id))
    await call.answer()


@router.message(AdminPayout.amount)
async def admin_payout(message: Message, state: FSMContext, session: AsyncSession, bot: Bot):
    if message.from_user.id != app_config.ADMIN_ID:
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

    bundle = await repo.get_full(session, order_id)
    order, client, category, creator_user = bundle
    order.status = OrderStatus.completed
    if creator_user:
        creator, creator_user_obj = creator_user
        creator.balance = (creator.balance or Decimal(0)) + amount
        await session.commit()
        await bot.send_message(
            creator_user_obj.tg_id,
            t("creator_balance_credited", creator_user_obj.lang, order_id=order_id, amount=amount)
            + t("review_upload_hint", creator_user_obj.lang),
        )
    else:
        await session.commit()

    await bot.send_message(client.tg_id, t("client_order_completed", client.lang, order_id=order_id))
    await message.answer(t("admin_final_done", Lang.ru, order_id=order_id, amount=amount))


@router.callback_query(F.data.startswith("ord:cancel:"))
async def cancel_order(call: CallbackQuery, session: AsyncSession, user: User, bot: Bot):
    order_id = int(call.data.split(":")[2])
    bundle = await repo.get_full(session, order_id)
    order, client, category, creator_user = bundle
    if order.client_id != user.id or order.status in (OrderStatus.completed, OrderStatus.cancelled):
        await call.answer()
        return
    order.status = OrderStatus.cancelled
    prev_creator = creator_user
    order.creator_id = None
    await session.commit()
    bundle = await repo.get_full(session, order_id)

    await _refresh(call, bundle, "client", user.lang)
    if prev_creator:
        await bot.send_message(prev_creator[1].tg_id,
                               t("order_cancelled_client", prev_creator[1].lang, order_id=order_id))
    await _push_card(bot, app_config.ADMIN_ID, bundle, "admin", Lang.ru)
    await call.answer()


@router.callback_query(F.data.startswith("ord:republish:"))
async def republish_order(call: CallbackQuery, session: AsyncSession, bot: Bot):
    if call.from_user.id != app_config.ADMIN_ID:
        await call.answer()
        return
    order_id = int(call.data.split(":")[2])
    bundle = await repo.get_full(session, order_id)
    order, client, category, creator_user = bundle
    if order.status != OrderStatus.cancelled:
        await call.answer()
        return
    await repo.set_status(session, order_id, OrderStatus.published)
    order, client, category, _ = await repo.get_full(session, order_id)

    from bot.handlers.orders import publish_tender

    await publish_tender(bot, session, order, category, client)
    await call.message.edit_text(call.message.html_text + f"\n\n♻️ {t('notify_republished', Lang.ru, order_id=order_id)}")
    await call.answer()
