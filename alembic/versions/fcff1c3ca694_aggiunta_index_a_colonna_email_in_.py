"""Aggiunta index a colonna email in customers

Revision ID: fcff1c3ca694
Revises: 1a6554b21019
Create Date: 2024-04-08 11:11:39.083525

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fcff1c3ca694'
down_revision: Union[str, None] = '1a6554b21019'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index('idx_email', 'customers', ['email'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_email', 'customers')
