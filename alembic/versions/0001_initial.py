"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-07-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


lang = sa.Enum("ru", "en", name="lang")
role = sa.Enum("client", "creator", name="role")
creator_status = sa.Enum("pending", "approved", "blocked", name="creatorstatus")
moderation_status = sa.Enum("pending", "approved", "rejected", name="moderationstatus")
order_status = sa.Enum(
    "published", "taken", "await_prepay", "in_progress",
    "await_final", "completed", "cancelled", name="orderstatus",
)


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tg_id", sa.BigInteger, nullable=False),
        sa.Column("username", sa.String(64)),
        sa.Column("nickname", sa.String(64)),
        sa.Column("lang", lang, nullable=False, server_default="ru"),
        sa.Column("role", role),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tg_id"),
    )
    op.create_index("ix_users_tg_id", "users", ["tg_id"])

    op.create_table(
        "creators",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", creator_status, nullable=False, server_default="pending"),
        sa.Column("service", sa.String(128)),
        sa.Column("experience", sa.Text),
        sa.Column("portfolio", sa.Text),
        sa.Column("socials", sa.Text),
        sa.Column("balance", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id"),
    )

    op.create_table(
        "categories",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("title_ru", sa.String(128), nullable=False),
        sa.Column("title_en", sa.String(128), nullable=False),
        sa.Column("thread_id", sa.BigInteger),
        sa.Column("is_custom", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("code"),
    )

    op.create_table(
        "works",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("creator_id", sa.Integer, sa.ForeignKey("creators.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category_id", sa.Integer, sa.ForeignKey("categories.id"), nullable=False),
        sa.Column("title", sa.String(128), nullable=False),
        sa.Column("cover_file_id", sa.String(256)),
        sa.Column("audio_file_id", sa.String(256)),
        sa.Column("genre", sa.String(64)),
        sa.Column("key", sa.String(16)),
        sa.Column("bpm", sa.Integer),
        sa.Column("price_rent", sa.Numeric(12, 2)),
        sa.Column("price_buy", sa.Numeric(12, 2)),
        sa.Column("moderation_status", moderation_status, nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "orders",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("client_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("category_id", sa.Integer, sa.ForeignKey("categories.id"), nullable=False),
        sa.Column("brief", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("creator_id", sa.Integer, sa.ForeignKey("creators.id")),
        sa.Column("status", order_status, nullable=False, server_default="published"),
        sa.Column("amount", sa.Numeric(12, 2)),
        sa.Column("tender_message_id", sa.BigInteger),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "reviews",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("creator_id", sa.Integer, sa.ForeignKey("creators.id", ondelete="CASCADE"), nullable=False),
        sa.Column("photo_file_id", sa.String(256), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("reviews")
    op.drop_table("orders")
    op.drop_table("works")
    op.drop_table("categories")
    op.drop_table("creators")
    op.drop_index("ix_users_tg_id", table_name="users")
    op.drop_table("users")
    for e in (order_status, moderation_status, creator_status, role, lang):
        e.drop(op.get_bind(), checkfirst=True)
