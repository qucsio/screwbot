"""creator profiles per direction

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-26

Раньше «исполнитель» был один на человека с одним статусом модерации. Теперь
у человека может быть несколько профилей — по одному на направление, каждый
одобряется отдельно. Статус самого исполнителя становится общим: approved
(обычный) или blocked (забанен целиком).

Перенос данных: направления берём из категорий уже загруженных работ; если
работ нет — заводим один профиль «beats», остальные исполнитель добавит сам.
Элементы портфолио остаются без профиля (profile_id = NULL) и показываются
во всех профилях автора.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# та же таблица соответствий, что и в bot/categories.py
DIRECTION_BY_CATEGORY = {
    "ready_beats": "beats",
    "custom_beats": "beats",
    "mixing": "mixing",
    "ghostwriting": "lyrics",
    "ready_visual": "visual",
    "visual": "visual",
    "ready_video": "video",
    "videographer": "video",
    "editing": "video",
    "photo": "photo",
}
DEFAULT_DIRECTION = "beats"

# тип уже существует в БД (создан миграцией 0001) — только используем
creator_status = postgresql.ENUM(
    "pending", "approved", "blocked", name="creatorstatus", create_type=False
)


def upgrade() -> None:
    op.create_table(
        "creator_profiles",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "creator_id", sa.Integer,
            sa.ForeignKey("creators.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("direction", sa.String(16), nullable=False),
        sa.Column("status", creator_status, nullable=False, server_default="pending"),
        sa.Column("about", sa.Text),
        sa.Column("links", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("creator_id", "direction", name="uq_creator_profiles_creator_direction"),
    )
    op.create_index("ix_creator_profiles_creator_id", "creator_profiles", ["creator_id"])

    op.add_column("portfolio_items", sa.Column("profile_id", sa.Integer))
    op.create_foreign_key(
        "fk_portfolio_items_profile", "portfolio_items", "creator_profiles",
        ["profile_id"], ["id"], ondelete="CASCADE",
    )
    op.create_index("ix_portfolio_items_profile_id", "portfolio_items", ["profile_id"])

    conn = op.get_bind()
    creators = conn.execute(
        sa.text("select id, status::text, experience, portfolio from creators")
    ).all()
    used = conn.execute(
        sa.text(
            "select distinct w.creator_id, c.code from works w "
            "join categories c on c.id = w.category_id"
        )
    ).all()
    by_creator: dict[int, set[str]] = {}
    for creator_id, code in used:
        direction = DIRECTION_BY_CATEGORY.get(code)
        if direction:
            by_creator.setdefault(creator_id, set()).add(direction)

    for creator_id, status, about, links in creators:
        for direction in sorted(by_creator.get(creator_id) or {DEFAULT_DIRECTION}):
            conn.execute(
                sa.text(
                    "insert into creator_profiles (creator_id, direction, status, about, links) "
                    "values (:cid, :dir, cast(:st as creatorstatus), :about, :links)"
                ),
                {"cid": creator_id, "dir": direction, "st": status, "about": about, "links": links},
            )
    # статус человека теперь «допущен/забанен»: ожидание переехало в профиль
    conn.execute(sa.text("update creators set status = 'approved' where status = 'pending'"))


def downgrade() -> None:
    op.drop_index("ix_portfolio_items_profile_id", table_name="portfolio_items")
    op.drop_constraint("fk_portfolio_items_profile", "portfolio_items", type_="foreignkey")
    op.drop_column("portfolio_items", "profile_id")
    op.drop_index("ix_creator_profiles_creator_id", table_name="creator_profiles")
    op.drop_table("creator_profiles")
