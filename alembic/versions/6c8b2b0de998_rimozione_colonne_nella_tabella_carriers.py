"""rimozione colonne nella tabella carriers

Revision ID: 6c8b2b0de998
Revises: 08468886e91c
Create Date: 2024-05-06 09:07:44.592354

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6c8b2b0de998'
down_revision: Union[str, None] = '08468886e91c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column('carriers', 'min_weight')
    op.drop_column('carriers', 'max_weight')
    op.drop_column('carriers', 'price')
    op.drop_column('carriers', 'api_key')


def downgrade() -> None:
    op.add_column('carriers', sa.Column('min_weight', sa.Float(), nullable=True))
    op.add_column('carriers', sa.Column('max_weight', sa.Float(), nullable=True))
    op.add_column('carriers', sa.Column('price', sa.Float(), nullable=True))
    op.add_column('carriers', sa.Column('api_key', sa.String(length=255), nullable=True))
