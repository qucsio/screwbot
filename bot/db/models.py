from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# --- Enums ---------------------------------------------------------------


class Lang(str, enum.Enum):
    ru = "ru"
    en = "en"


class Role(str, enum.Enum):
    client = "client"
    creator = "creator"


class CreatorStatus(str, enum.Enum):
    pending = "pending"      # заявка на модерации
    approved = "approved"
    blocked = "blocked"


class ModerationStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class OrderStatus(str, enum.Enum):
    published = "published"          # тендер в чате категории
    taken = "taken"                  # исполнитель взял
    await_prepay = "await_prepay"    # ждём 50%
    in_progress = "in_progress"      # предоплата подтверждена, работа идёт
    await_final = "await_final"      # демо утверждено, ждём остальные 50%
    completed = "completed"
    cancelled = "cancelled"


# --- Tables --------------------------------------------------------------


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(64))
    nickname: Mapped[str | None] = mapped_column(String(64))
    lang: Mapped[Lang] = mapped_column(SAEnum(Lang), default=Lang.ru)
    role: Mapped[Role | None] = mapped_column(SAEnum(Role))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    creator: Mapped[Creator | None] = relationship(
        back_populates="user", uselist=False
    )


class Creator(Base):
    __tablename__ = "creators"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    status: Mapped[CreatorStatus] = mapped_column(
        SAEnum(CreatorStatus), default=CreatorStatus.pending
    )
    service: Mapped[str | None] = mapped_column(String(128))     # заявленная услуга
    experience: Mapped[str | None] = mapped_column(Text)
    portfolio: Mapped[str | None] = mapped_column(Text)          # ссылки/описание
    socials: Mapped[str | None] = mapped_column(Text)
    balance: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="creator")


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)   # beats, mixing, ...
    title_ru: Mapped[str] = mapped_column(String(128))
    title_en: Mapped[str] = mapped_column(String(128))
    thread_id: Mapped[int | None] = mapped_column(BigInteger)    # topic тендеров
    is_custom: Mapped[bool] = mapped_column(Boolean, default=True)  # услуга на заказ


class Work(Base):
    """Готовая работа в каталоге (бит, обложка, шаблон и т.д.)."""

    __tablename__ = "works"

    id: Mapped[int] = mapped_column(primary_key=True)
    creator_id: Mapped[int] = mapped_column(ForeignKey("creators.id", ondelete="CASCADE"))
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))
    title: Mapped[str] = mapped_column(String(128))
    cover_file_id: Mapped[str | None] = mapped_column(String(256))
    audio_file_id: Mapped[str | None] = mapped_column(String(256))

    # теги (для битов)
    genre: Mapped[str | None] = mapped_column(String(64))
    key: Mapped[str | None] = mapped_column(String(16))     # тональность
    bpm: Mapped[int | None] = mapped_column()

    price_rent: Mapped[float | None] = mapped_column(Numeric(12, 2))
    price_buy: Mapped[float | None] = mapped_column(Numeric(12, 2))

    moderation_status: Mapped[ModerationStatus] = mapped_column(
        SAEnum(ModerationStatus), default=ModerationStatus.pending
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Order(Base):
    """Заказ по ТЗ (тендер)."""

    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))
    brief: Mapped[dict] = mapped_column(JSONB, default=dict)   # заполненное ТЗ
    creator_id: Mapped[int | None] = mapped_column(ForeignKey("creators.id"))
    status: Mapped[OrderStatus] = mapped_column(
        SAEnum(OrderStatus), default=OrderStatus.published
    )
    amount: Mapped[float | None] = mapped_column(Numeric(12, 2))
    tender_message_id: Mapped[int | None] = mapped_column(BigInteger)  # id поста-тендера
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    creator_id: Mapped[int] = mapped_column(ForeignKey("creators.id", ondelete="CASCADE"))
    photo_file_id: Mapped[str] = mapped_column(String(256))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
