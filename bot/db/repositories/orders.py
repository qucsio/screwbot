from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import Order, OrderStatus


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
