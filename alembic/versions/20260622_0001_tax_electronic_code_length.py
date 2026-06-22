"""taxes.electronic_code VARCHAR(10) -> VARCHAR(255) (FE handoff)

Revision ID: 20260622_0001
Revises: 20260605_0001
Create Date: 2026-06-22

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260622_0001"
down_revision: Union[str, None] = "20260605_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "taxes",
        "electronic_code",
        existing_type=sa.String(length=10),
        type_=sa.String(length=255),
        existing_nullable=True,
        existing_server_default=sa.text("''"),
    )


def downgrade() -> None:
    op.alter_column(
        "taxes",
        "electronic_code",
        existing_type=sa.String(length=255),
        type_=sa.String(length=10),
        existing_nullable=True,
        existing_server_default=sa.text("''"),
    )
