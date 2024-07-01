"""Ripristino revisione mancante

Revision ID: 9d980f91bdf9
Revises: 9e6e88c3e77a
Create Date: 2024-05-22 17:00:20.637457

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9d980f91bdf9'
down_revision: Union[str, None] = '9e6e88c3e77a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('roles', sa.Column('permissions', sa.String(10), default='r'))


def downgrade() -> None:
    op.drop_column('roles', 'permissions')
