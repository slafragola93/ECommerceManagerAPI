"""empty message

Revision ID: eb4e45f69598
Revises: 9d980f91bdf9
Create Date: 2024-06-26 10:36:48.849481

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'eb4e45f69598'
down_revision: Union[str, None] = '9d980f91bdf9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('invoices', sa.Column('date_add', sa.Date))


def downgrade() -> None:
    op.drop_column('invoices', 'date_add')
