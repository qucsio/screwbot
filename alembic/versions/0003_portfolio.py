"""portfolio media items

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


media_type = sa.Enum("photo", "video", "audio", "document", name="mediatype")


def upgrade() -> None:
    media_type.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "portfolio_items",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "creator_id",
            sa.Integer,
            sa.ForeignKey("creators.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("media_type", media_type, nullable=False),
        sa.Column("file_id", sa.String(256), nullable=False),
        sa.Column("caption", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_portfolio_items_creator_id", "portfolio_items", ["creator_id"])


def downgrade() -> None:
    op.drop_index("ix_portfolio_items_creator_id", table_name="portfolio_items")
    op.drop_table("portfolio_items")
    media_type.drop(op.get_bind(), checkfirst=True)
