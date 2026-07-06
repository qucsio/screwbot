from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import (
    Category,
    Creator,
    CreatorStatus,
    ModerationStatus,
    User,
    Work,
)


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
        .join(Creator, Creator.id == Work.creator_id)
        .where(
            Work.category_id == category_id,
            Work.moderation_status == ModerationStatus.approved,
            Creator.status == CreatorStatus.approved,
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
    q = (
        select(Work.id)
        .join(Creator, Creator.id == Work.creator_id)
        .where(
            Work.category_id == category_id,
            Work.moderation_status == ModerationStatus.approved,
            Creator.status == CreatorStatus.approved,
        )
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


async def list_creator_works(session: AsyncSession, creator_id: int) -> list[Work]:
    res = await session.execute(
        select(Work).where(Work.creator_id == creator_id).order_by(Work.id.desc())
    )
    return list(res.scalars().all())


async def get_creator_work(session: AsyncSession, work_id: int, creator_id: int) -> Work | None:
    """Работа с проверкой владельца — чтобы нельзя было редактировать чужую."""
    res = await session.execute(
        select(Work).where(Work.id == work_id, Work.creator_id == creator_id)
    )
    return res.scalar_one_or_none()


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


# --- Админские выборки ---------------------------------------------------


async def list_creators(session: AsyncSession) -> list[tuple[Creator, User]]:
    res = await session.execute(
        select(Creator, User)
        .join(User, User.id == Creator.user_id)
        .order_by(Creator.id.desc())
    )
    return [(r[0], r[1]) for r in res.all()]


async def get_creator_full(session: AsyncSession, creator_id: int) -> tuple[Creator, User] | None:
    res = await session.execute(
        select(Creator, User).join(User, User.id == Creator.user_id).where(Creator.id == creator_id)
    )
    row = res.first()
    return (row[0], row[1]) if row else None


async def find_user_by_query(session: AsyncSession, query: str) -> User | None:
    """Поиск пользователя по @username или числовому tg_id."""
    q = query.strip().lstrip("@")
    if q.isdigit():
        res = await session.execute(select(User).where(User.tg_id == int(q)))
    else:
        res = await session.execute(select(User).where(User.username.ilike(q)))
    return res.scalar_one_or_none()


async def list_recent_works(session: AsyncSession, limit: int = 30) -> list[Work]:
    res = await session.execute(select(Work).order_by(Work.id.desc()).limit(limit))
    return list(res.scalars().all())


async def get_work(session: AsyncSession, work_id: int) -> Work | None:
    return await session.get(Work, work_id)
