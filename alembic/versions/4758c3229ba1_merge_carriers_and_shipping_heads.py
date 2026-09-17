"""merge_carriers_and_shipping_heads

Revision ID: 4758c3229ba1
Revises: c6a9f124459b, e69469dad6a8
Create Date: 2026-01-27 11:27:26.380730

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4758c3229ba1'
down_revision: Union[str, None] = ('c6a9f124459b', 'e69469dad6a8')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
