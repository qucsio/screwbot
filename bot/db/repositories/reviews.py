from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import Review


async def add_review(session: AsyncSession, creator_id: int, photo_file_id: str) -> Review:
    review = Review(creator_id=creator_id, photo_file_id=photo_file_id)
    session.add(review)
    await session.commit()
    return review


async def last_reviews(session: AsyncSession, limit: int = 10) -> list[str]:
    """photo_file_id последних отзывов, новые первыми."""
    res = await session.execute(
        select(Review.photo_file_id).order_by(Review.id.desc()).limit(limit)
    )
    return list(res.scalars().all())
