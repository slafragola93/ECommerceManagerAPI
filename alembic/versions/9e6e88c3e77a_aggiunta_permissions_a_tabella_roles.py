"""aggiunta permissions a tabella roles

Revision ID: 9e6e88c3e77a
Revises: 6c8b2b0de998
Create Date: 2024-05-22 16:53:35.212136

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9e6e88c3e77a'
down_revision: Union[str, None] = '6c8b2b0de998'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('roles', sa.Column('permissions', sa.String(), default='r'))


def downgrade() -> None:
    op.drop_column('roles', 'permissions')
