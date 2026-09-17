"""Add is_multishipping column to orders

Revision ID: d2e80f84ce12
Revises: df255696fd9c
Create Date: 2026-01-20 11:13:06.455220

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = 'd2e80f84ce12'
down_revision: Union[str, None] = 'df255696fd9c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()
    
    # Verifica se la colonna esiste già
    result = connection.execute(text("""
        SELECT COUNT(*) as count
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
        AND TABLE_NAME = 'orders'
        AND COLUMN_NAME = 'is_multishipping'
    """))
    column_exists = result.fetchone()[0] > 0
    
    if not column_exists:
        # Aggiungi colonna is_multishipping
        op.add_column('orders', 
                     sa.Column('is_multishipping', sa.Integer(), 
                              nullable=False, 
                              server_default='0',
                              comment='1 se ordine in multispedizione'))


def downgrade() -> None:
    connection = op.get_bind()
    
    # Verifica se la colonna esiste
    result = connection.execute(text("""
        SELECT COUNT(*) as count
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
        AND TABLE_NAME = 'orders'
        AND COLUMN_NAME = 'is_multishipping'
    """))
    column_exists = result.fetchone()[0] > 0
    
    if column_exists:
        # Rimuovi colonna is_multishipping
        op.drop_column('orders', 'is_multishipping')
