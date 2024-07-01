"""rimozione tabella zone

Revision ID: 08468886e91c
Revises: 0ffd07cd7fd1
Create Date: 2024-05-03 09:46:24.973531

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '08468886e91c'
down_revision: Union[str, None] = '0ffd07cd7fd1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table('zones')


def downgrade() -> None:
    op.create_table(
        'zones',
        sa.Column('id_zone', sa.Integer, primary_key=True),
        sa.Column('name', sa.String(50), nullable=False)
    )
