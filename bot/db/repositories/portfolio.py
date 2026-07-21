from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import MediaType, PortfolioItem


async def list_items(session: AsyncSession, creator_id: int) -> list[PortfolioItem]:
    res = await session.execute(
        select(PortfolioItem)
        .where(PortfolioItem.creator_id == creator_id)
        .order_by(PortfolioItem.id)
    )
    return list(res.scalars().all())


async def count(session: AsyncSession, creator_id: int) -> int:
    res = await session.execute(
        select(func.count(PortfolioItem.id)).where(
            PortfolioItem.creator_id == creator_id
        )
    )
    return int(res.scalar_one())


async def get_item(session: AsyncSession, item_id: int, creator_id: int) -> PortfolioItem | None:
    res = await session.execute(
        select(PortfolioItem).where(
            PortfolioItem.id == item_id,
            PortfolioItem.creator_id == creator_id,
        )
    )
    return res.scalar_one_or_none()


async def add_item(
    session: AsyncSession,
    creator_id: int,
    media_type: MediaType,
    file_id: str,
    caption: str | None,
) -> PortfolioItem:
    item = PortfolioItem(
        creator_id=creator_id,
        media_type=media_type,
        file_id=file_id,
        caption=caption,
    )
    session.add(item)
    await session.commit()
    return item


async def delete_item(session: AsyncSession, item_id: int, creator_id: int) -> None:
    await session.execute(
        delete(PortfolioItem).where(
            PortfolioItem.id == item_id,
            PortfolioItem.creator_id == creator_id,
        )
    )
    await session.commit()
