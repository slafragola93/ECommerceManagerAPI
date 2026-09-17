"""add_departure_depot_to_brt_configurations

Revision ID: 4000ddbfb949
Revises: 6ed9b7749d11
Create Date: 2025-11-18 12:23:35.103658

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4000ddbfb949'
down_revision: Union[str, None] = '6ed9b7749d11'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('brt_configurations', sa.Column('departure_depot', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('brt_configurations', 'departure_depot')
