"""preferred creator chosen by the client

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-26

После заполнения ТЗ клиент выбирает исполнителя по профилю направления.
Выбранного отмечаем в заказе: его тегают в топике и зовут в личку, но взять
заказ по-прежнему может любой исполнитель с профилем этого направления.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("preferred_creator_id", sa.Integer))
    op.create_foreign_key(
        "fk_orders_preferred_creator", "orders", "creators", ["preferred_creator_id"], ["id"]
    )


def downgrade() -> None:
    op.drop_constraint("fk_orders_preferred_creator", "orders", type_="foreignkey")
    op.drop_column("orders", "preferred_creator_id")
