"""Rimozione attributo UNIQUE da campo EMAIL della tabella customers

Revision ID: 1a6554b21019
Revises: 
Create Date: 2024-04-08 11:05:32.560213

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1a6554b21019'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index('idx_email', 'customers', ['email'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_email', 'customers')
