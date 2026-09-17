"""add_updated_at_to_orders

Revision ID: 9e03c7965b78
Revises: 672f8844fa13
Create Date: 2025-12-01 16:34:32.433919

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = '9e03c7965b78'
down_revision: Union[str, None] = '672f8844fa13'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Check if column already exists before adding it
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    columns = [col['name'] for col in inspector.get_columns('orders')]
    
    if 'updated_at' not in columns:
        # Aggiungi colonna updated_at alla tabella orders
        op.add_column('orders', sa.Column('updated_at', sa.String(19), nullable=True))
        
        # Popola updated_at con date_add formattato per ordini esistenti
        op.execute(text("""
            UPDATE orders 
            SET updated_at = DATE_FORMAT(date_add, '%d-%m-%Y %H:%i:%s')
            WHERE updated_at IS NULL AND date_add IS NOT NULL
        """))


def downgrade() -> None:
    # Check if column exists before dropping it
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    columns = [col['name'] for col in inspector.get_columns('orders')]
    
    if 'updated_at' in columns:
        # Rimuovi colonna updated_at dalla tabella orders
        op.drop_column('orders', 'updated_at')
