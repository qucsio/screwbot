from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import Category, Creator, Order, OrderStatus, User

# Статусы, которые показываем в «Мои заказы» (активные + недавно завершённые).
VISIBLE_STATUSES = [
    OrderStatus.taken,
    OrderStatus.await_prepay,
    OrderStatus.in_progress,
    OrderStatus.demo_review,
    OrderStatus.await_final,
    OrderStatus.completed,
]


async def claim_order(session: AsyncSession, order_id: int, creator_id: int) -> bool:
    """Атомарно закрепляет заказ за исполнителем.

    Возвращает True, если удалось (заказ был published). Защита от гонки:
    UPDATE ... WHERE status='published' — второй нажавший получит 0 строк.
    """
    result = await session.execute(
        update(Order)
        .where(Order.id == order_id, Order.status == OrderStatus.published)
        .values(creator_id=creator_id, status=OrderStatus.taken)
    )
    await session.commit()
    return result.rowcount == 1


async def set_status(session: AsyncSession, order_id: int, status: OrderStatus) -> None:
    await session.execute(
        update(Order).where(Order.id == order_id).values(status=status)
    )
    await session.commit()


async def list_for_client(session: AsyncSession, client_user_id: int) -> list[Order]:
    res = await session.execute(
        select(Order)
        .where(Order.client_id == client_user_id, Order.status.in_(VISIBLE_STATUSES))
        .order_by(Order.id.desc())
        .limit(20)
    )
    return list(res.scalars().all())


async def list_for_creator(session: AsyncSession, creator_id: int) -> list[Order]:
    res = await session.execute(
        select(Order)
        .where(Order.creator_id == creator_id, Order.status.in_(VISIBLE_STATUSES))
        .order_by(Order.id.desc())
        .limit(20)
    )
    return list(res.scalars().all())


async def get_full(session: AsyncSession, order_id: int):
    """Возвращает (order, client, category, creator_user|None)."""
    order = await session.get(Order, order_id)
    if order is None:
        return None
    client = await session.get(User, order.client_id)
    category = await session.get(Category, order.category_id)
    creator_user = None
    if order.creator_id:
        res = await session.execute(
            select(Creator, User)
            .join(User, User.id == Creator.user_id)
            .where(Creator.id == order.creator_id)
        )
        row = res.first()
        if row:
            creator_user = (row[0], row[1])
    return order, client, category, creator_user
