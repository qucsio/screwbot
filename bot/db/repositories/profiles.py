"""Профили исполнителя по направлениям: доступ, модерация, витрина для клиента."""
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.categories import categories_of_direction
from bot.db.models import (
    Category,
    Creator,
    CreatorProfile,
    CreatorStatus,
    ModerationStatus,
    User,
    Work,
)


async def list_profiles(session: AsyncSession, creator_id: int) -> list[CreatorProfile]:
    res = await session.execute(
        select(CreatorProfile).where(CreatorProfile.creator_id == creator_id).order_by(CreatorProfile.id)
    )
    return list(res.scalars().all())


async def get_profile_by_direction(
    session: AsyncSession, creator_id: int, direction: str
) -> CreatorProfile | None:
    res = await session.execute(
        select(CreatorProfile).where(
            CreatorProfile.creator_id == creator_id, CreatorProfile.direction == direction
        )
    )
    return res.scalar_one_or_none()


async def get_own_profile(session: AsyncSession, profile_id: int, creator_id: int) -> CreatorProfile | None:
    """Профиль с проверкой владельца — чтобы нельзя было править чужой."""
    res = await session.execute(
        select(CreatorProfile).where(CreatorProfile.id == profile_id, CreatorProfile.creator_id == creator_id)
    )
    return res.scalar_one_or_none()


async def profile_with_owner(
    session: AsyncSession, profile_id: int
) -> tuple[CreatorProfile, Creator, User] | None:
    res = await session.execute(
        select(CreatorProfile, Creator, User)
        .join(Creator, Creator.id == CreatorProfile.creator_id)
        .join(User, User.id == Creator.user_id)
        .where(CreatorProfile.id == profile_id)
    )
    row = res.first()
    return (row[0], row[1], row[2]) if row else None


async def approved_profile(session: AsyncSession, user_id: int, direction: str) -> CreatorProfile | None:
    """Одобренный профиль пользователя по направлению (и сам исполнитель не заблокирован).

    Это и есть право взять заказ или выложить работу в этом направлении.
    """
    res = await session.execute(
        select(CreatorProfile)
        .join(Creator, Creator.id == CreatorProfile.creator_id)
        .where(
            Creator.user_id == user_id,
            Creator.status == CreatorStatus.approved,
            CreatorProfile.direction == direction,
            CreatorProfile.status == CreatorStatus.approved,
        )
    )
    return res.scalar_one_or_none()


async def menu_status(session: AsyncSession, user_id: int) -> CreatorStatus | None:
    """Что показывать в главном меню: панель, «на рассмотрении», ничего."""
    creator = (await session.execute(select(Creator).where(Creator.user_id == user_id))).scalar_one_or_none()
    if creator is None:
        return None
    if creator.status == CreatorStatus.blocked:
        return CreatorStatus.blocked
    res = await session.execute(
        select(CreatorProfile.status).where(CreatorProfile.creator_id == creator.id)
    )
    statuses = set(res.scalars().all())
    if CreatorStatus.approved in statuses:
        return CreatorStatus.approved
    if CreatorStatus.pending in statuses:
        return CreatorStatus.pending
    return CreatorStatus.blocked if statuses else None


async def list_approved_by_direction(
    session: AsyncSession, direction: str
) -> list[tuple[CreatorProfile, Creator, User]]:
    """Витрина исполнителей направления — из неё клиент выбирает после ТЗ."""
    res = await session.execute(
        select(CreatorProfile, Creator, User)
        .join(Creator, Creator.id == CreatorProfile.creator_id)
        .join(User, User.id == Creator.user_id)
        .where(
            CreatorProfile.direction == direction,
            CreatorProfile.status == CreatorStatus.approved,
            Creator.status == CreatorStatus.approved,
        )
        .order_by(CreatorProfile.id)
    )
    return [(r[0], r[1], r[2]) for r in res.all()]


async def list_pending_profiles(
    session: AsyncSession, limit: int = 30
) -> list[tuple[CreatorProfile, Creator, User]]:
    """Заявки по направлениям, ждущие решения (старые первыми)."""
    res = await session.execute(
        select(CreatorProfile, Creator, User)
        .join(Creator, Creator.id == CreatorProfile.creator_id)
        .join(User, User.id == Creator.user_id)
        .where(CreatorProfile.status == CreatorStatus.pending)
        .order_by(CreatorProfile.id)
        .limit(limit)
    )
    return [(r[0], r[1], r[2]) for r in res.all()]


async def count_approved_works(session: AsyncSession, creator_id: int, direction: str) -> int:
    """Сколько одобренных работ у исполнителя в этом направлении (для витрины)."""
    codes = [c.code for c in categories_of_direction(direction)]
    if not codes:
        return 0
    res = await session.execute(
        select(func.count(Work.id))
        .join(Category, Category.id == Work.category_id)
        .where(
            Work.creator_id == creator_id,
            Category.code.in_(codes),
            Work.moderation_status == ModerationStatus.approved,
        )
    )
    return int(res.scalar_one())
