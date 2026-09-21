"""work audio kind (audio | document)

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # NULL у старых записей = "audio" (раньше иначе и не отправлялось)
    op.add_column("works", sa.Column("audio_kind", sa.String(16)))


def downgrade() -> None:
    op.drop_column("works", "audio_kind")
