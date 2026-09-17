"""remove_price_with_tax_from_carrier_assignments

Revision ID: 68c4974dd16f
Revises: 76a0ebef4812
Create Date: 2025-11-28 11:56:22.677498

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '68c4974dd16f'
down_revision: Union[str, None] = '76a0ebef4812'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
