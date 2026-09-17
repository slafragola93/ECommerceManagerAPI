"""merge heads

Revision ID: 349dfd185497
Revises: 6c7678f2fc49, f4157b4e4330
Create Date: 2026-01-15 08:48:37.266724

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '349dfd185497'
down_revision: Union[str, None] = ('6c7678f2fc49', 'f4157b4e4330')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
