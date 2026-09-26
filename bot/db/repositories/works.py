from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import (
    Category,
    Creator,
    CreatorProfile,
    CreatorStatus,
    ModerationStatus,
    User,
    Work,
)


async def get_category_by_code(session: AsyncSession, code: str) -> Category | None:
    res = await session.execute(select(Category).where(Category.code == code))
    return res.scalar_one_or_none()


async def get_creator(session: AsyncSession, user_id: int) -> Creator | None:
    """Строка исполнителя в любом статусе (pending/approved/blocked) или None."""
    res = await session.execute(
        select(Creator).where(Creator.user_id == user_id)
    )
    return res.scalar_one_or_none()


async def get_approved_creator(session: AsyncSession, user_id: int) -> Creator | None:
    """Исполнитель, которому открыта панель: не заблокирован и имеет хотя бы один
    одобренный профиль. Право на конкретное направление проверяет
    profiles.approved_profile()."""
    res = await session.execute(
        select(Creator)
        .join(CreatorProfile, CreatorProfile.creator_id == Creator.id)
        .where(
            Creator.user_id == user_id,
            Creator.status == CreatorStatus.approved,
            CreatorProfile.status == CreatorStatus.approved,
        )
        .limit(1)
    )
    return res.scalars().first()


def _visible_works(direction: str):
    """Работы, которые видит клиент: одобрены и автор одобрен по этому направлению."""
    return (
        select(Work)
        .join(Creator, Creator.id == Work.creator_id)
        .join(
            CreatorProfile,
            (CreatorProfile.creator_id == Creator.id) & (CreatorProfile.direction == direction),
        )
        .where(
            Work.moderation_status == ModerationStatus.approved,
            Creator.status == CreatorStatus.approved,
            CreatorProfile.status == CreatorStatus.approved,
        )
    )


async def approved_beat_genres(session: AsyncSession, category_id: int, direction: str) -> list[str]:
    q = _visible_works(direction).with_only_columns(Work.genre).where(
        Work.category_id == category_id, Work.genre.is_not(None)
    ).distinct()
    res = await session.execute(q)
    return sorted({g for g in res.scalars().all() if g})


async def filter_beats(
    session: AsyncSession,
    category_id: int,
    direction: str,
    genre: str | None = None,
    key: str | None = None,
    bpm_min: int | None = None,
    bpm_max: int | None = None,
) -> list[int]:
    """Возвращает id одобренных работ категории под фильтр, новые сверху."""
    q = _visible_works(direction).with_only_columns(Work.id).where(Work.category_id == category_id)
    if genre:
        q = q.where(Work.genre == genre)
    if key:
        # тональность — свободный текст исполнителя: «Am» и «am» — одно и то же
        q = q.where(func.lower(func.trim(Work.key)) == key.strip().lower())
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


async def list_creators(
    session: AsyncSession, offset: int = 0, limit: int | None = None
) -> list[tuple[Creator, User]]:
    q = (
        select(Creator, User)
        .join(User, User.id == Creator.user_id)
        .order_by(Creator.id.desc())
        .offset(offset)
    )
    if limit is not None:
        q = q.limit(limit)
    res = await session.execute(q)
    return [(r[0], r[1]) for r in res.all()]


async def count_creators(session: AsyncSession) -> int:
    return int(await session.scalar(select(func.count(Creator.id))))


async def list_pending_creators(session: AsyncSession, limit: int = 30) -> list[tuple[Creator, User]]:
    """Заявки исполнителей, ждущие решения (старые первыми)."""
    res = await session.execute(
        select(Creator, User)
        .join(User, User.id == Creator.user_id)
        .where(Creator.status == CreatorStatus.pending)
        .order_by(Creator.id)
        .limit(limit)
    )
    return [(r[0], r[1]) for r in res.all()]


async def list_pending_works(session: AsyncSession, limit: int = 30) -> list[Work]:
    """Работы на модерации (старые первыми)."""
    res = await session.execute(
        select(Work)
        .where(Work.moderation_status == ModerationStatus.pending)
        .order_by(Work.id)
        .limit(limit)
    )
    return list(res.scalars().all())


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


async def work_catalog_type(session: AsyncSession, work: Work) -> str:
    """"beat" | "visual" — по коду категории работы (для правильного рендера карточки)."""
    from bot.categories import by_code

    category = await session.get(Category, work.category_id)
    cdef = by_code(category.code) if category else None
    return (cdef.catalog_type if cdef else "") or "beat"
