"""change_shipping_date_add_to_datetime

Revision ID: ae595f42fb39
Revises: 6b6f2f043e54
Create Date: 2025-11-20 16:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = 'ae595f42fb39'
down_revision: Union[str, None] = '6b6f2f043e54'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### Change shipments.date_add from DATE to DateTime ###
    op.alter_column('shipments', 'date_add',
               existing_type=sa.DATE(),
               type_=sa.DateTime(),
               existing_nullable=True)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### Revert shipments.date_add from DateTime to DATE ###
    op.alter_column('shipments', 'date_add',
               existing_type=sa.DateTime(),
               type_=sa.DATE(),
               existing_nullable=True)
    # ### end Alembic commands ###
