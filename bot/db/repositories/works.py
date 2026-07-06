from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import Category, Creator, ModerationStatus, User, Work


async def get_category_by_code(session: AsyncSession, code: str) -> Category | None:
    res = await session.execute(select(Category).where(Category.code == code))
    return res.scalar_one_or_none()


async def get_approved_creator(session: AsyncSession, user_id: int) -> Creator | None:
    from bot.db.models import CreatorStatus

    res = await session.execute(
        select(Creator).where(
            Creator.user_id == user_id,
            Creator.status == CreatorStatus.approved,
        )
    )
    return res.scalar_one_or_none()


async def approved_beat_genres(session: AsyncSession, category_id: int) -> list[str]:
    res = await session.execute(
        select(Work.genre)
        .where(
            Work.category_id == category_id,
            Work.moderation_status == ModerationStatus.approved,
            Work.genre.is_not(None),
        )
        .distinct()
    )
    return sorted({g for g in res.scalars().all() if g})


async def filter_beats(
    session: AsyncSession,
    category_id: int,
    genre: str | None = None,
    key: str | None = None,
    bpm_min: int | None = None,
    bpm_max: int | None = None,
) -> list[int]:
    """Возвращает id одобренных битов под фильтр, новые сверху."""
    q = select(Work.id).where(
        Work.category_id == category_id,
        Work.moderation_status == ModerationStatus.approved,
    )
    if genre:
        q = q.where(Work.genre == genre)
    if key:
        q = q.where(Work.key == key)
    if bpm_min is not None:
        q = q.where(Work.bpm >= bpm_min)
    if bpm_max is not None:
        q = q.where(Work.bpm <= bpm_max)
    q = q.order_by(Work.id.desc())
    res = await session.execute(q)
    return list(res.scalars().all())


async def get_work_with_author(
    session: AsyncSession, work_id: int
) -> tuple[Work, User] | None:
    res = await session.execute(
        select(Work, User)
        .join(Creator, Creator.id == Work.creator_id)
        .join(User, User.id == Creator.user_id)
        .where(Work.id == work_id)
    )
    row = res.first()
    return (row[0], row[1]) if row else None
