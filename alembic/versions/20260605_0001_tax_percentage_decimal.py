"""taxes.percentage Integer -> DECIMAL(5,2) (BE-ALIQ-05)

Revision ID: 20260605_0001
Revises:
Create Date: 2026-06-05

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260605_0001"
down_revision: Union[str, None] = "20260527_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "taxes",
        "percentage",
        existing_type=sa.Integer(),
        type_=sa.Numeric(5, 2),
        existing_nullable=True,
        server_default=sa.text("0.00"),
    )


def downgrade() -> None:
    op.alter_column(
        "taxes",
        "percentage",
        existing_type=sa.Numeric(5, 2),
        type_=sa.Integer(),
        existing_nullable=True,
        server_default=sa.text("0"),
    )
