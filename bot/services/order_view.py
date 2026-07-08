"""Единый рендер карточки заказа: текст + контекстные кнопки из статуса и роли.

viewer: "client" | "creator" | "admin". Кнопки рисуются по state-machine,
поэтому карточку можно показать в любой момент — действия всегда актуальны.
"""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot import app_config
from bot.categories import by_code
from bot.db.models import Category, Lang, Order, OrderStatus, User
from bot.locales import t

# Статусы, в которых контакты уже раскрыты (после подтверждения предоплаты).
_CONTACTS_OPEN = {
    OrderStatus.in_progress,
    OrderStatus.demo_review,
    OrderStatus.await_final,
    OrderStatus.completed,
}


def contact(user: User) -> str:
    if user.username:
        return f"@{user.username}"
    return f'<a href="tg://user?id={user.tg_id}">{user.nickname or "профиль"}</a>'


def render_order_card(
    order: Order,
    client: User,
    category: Category,
    creator_user: tuple | None,
    viewer: str,
    lang: Lang,
) -> tuple[str, InlineKeyboardMarkup | None]:
    title = category.title_en if lang == Lang.en else category.title_ru
    status_label = t(f"ostatus_{order.status.value}", lang)

    lines = [t("order_card_header", lang, order_id=order.id, title=title, status=status_label)]

    # ТЗ (для исполнителя и админа полезно; клиенту тоже не мешает)
    cdef = by_code(category.code)
    if cdef and order.brief:
        body = "\n".join(f"• {f.label}: {order.brief.get(f.key, '—')}" for f in cdef.fields)
        if body:
            lines.append("\n" + body)

    # контакты (после предоплаты)
    if order.status in _CONTACTS_OPEN and creator_user:
        if viewer == "client":
            lines.append("\n" + t("order_card_contact_creator", lang, contact=contact(creator_user[1])))
        elif viewer == "creator":
            lines.append("\n" + t("order_card_contact_client", lang, contact=contact(client)))

    # платёжные инструкции
    if viewer == "client":
        if order.status == OrderStatus.await_prepay:
            lines.append("\n" + t("order_first_pay", lang, details=app_config.PAYMENT_DETAILS))
        elif order.status == OrderStatus.await_final:
            lines.append("\n" + t("order_second_pay", lang, details=app_config.PAYMENT_DETAILS))

    text = "\n".join(lines)
    return text, _keyboard(order, viewer, lang)


def _btn(key: str, data: str, lang: Lang) -> list[InlineKeyboardButton]:
    return [InlineKeyboardButton(text=t(key, lang), callback_data=data)]


def _keyboard(order: Order, viewer: str, lang: Lang) -> InlineKeyboardMarkup | None:
    oid = order.id
    st = order.status
    rows: list[list[InlineKeyboardButton]] = []

    if viewer == "client":
        if st == OrderStatus.taken:
            rows.append(_btn("btn_confirm_creator", f"ord:confirmcreator:{oid}", lang))
            rows.append(_btn("btn_cancel_order", f"ord:cancel:{oid}", lang))
        elif st == OrderStatus.await_prepay:
            rows.append(_btn("btn_cancel_order", f"ord:cancel:{oid}", lang))
        elif st == OrderStatus.in_progress:
            rows.append(_btn("btn_cancel_order", f"ord:cancel:{oid}", lang))
        elif st == OrderStatus.demo_review:
            rows.append(_btn("btn_approve_demo", f"ord:approvedemo:{oid}", lang))
            rows.append(_btn("btn_cancel_order", f"ord:cancel:{oid}", lang))
        elif st == OrderStatus.await_final:
            rows.append(_btn("btn_paid", f"ord:paid:{oid}", lang))
            rows.append(_btn("btn_cancel_order", f"ord:cancel:{oid}", lang))

    elif viewer == "creator":
        if st == OrderStatus.in_progress:
            rows.append(_btn("btn_demo_done", f"ord:demodone:{oid}", lang))

    elif viewer == "admin":
        if st == OrderStatus.await_prepay:
            rows.append(_btn("btn_confirm_prepay", f"ord:prepay:{oid}", lang))
        elif st == OrderStatus.await_final:
            rows.append(_btn("btn_confirm_final", f"ord:final:{oid}", lang))
        elif st == OrderStatus.cancelled:
            rows.append(_btn("btn_republish", f"ord:republish:{oid}", lang))

    return InlineKeyboardMarkup(inline_keyboard=rows) if rows else None
