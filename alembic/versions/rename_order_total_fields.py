"""rename_order_total_fields

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2025-01-XX XX:XX:XX.XXXXXX

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    # ==================== ORDERS ====================
    if 'orders' in inspector.get_table_names():
        columns = [col['name'] for col in inspector.get_columns('orders')]
        
        # Rimuovi total_price_tax_excl se esiste
        if 'total_price_tax_excl' in columns:
            op.drop_column('orders', 'total_price_tax_excl')
            print("SUCCESS: Dropped total_price_tax_excl column from orders")
        
        # Rinomina total_with_tax -> total_price_with_tax
        if 'total_with_tax' in columns and 'total_price_with_tax' not in columns:
            op.alter_column('orders', 'total_with_tax',
                          new_column_name='total_price_with_tax',
                          existing_type=sa.Numeric(10, 5),
                          existing_nullable=False,
                          existing_server_default=sa.text('0'))
            print("SUCCESS: Renamed total_with_tax to total_price_with_tax in orders")
        elif 'total_price_with_tax' in columns:
            print("INFO: total_price_with_tax column already exists in orders")
        
        # Rinomina total_without_tax -> total_price_net
        if 'total_without_tax' in columns and 'total_price_net' not in columns:
            op.alter_column('orders', 'total_without_tax',
                          new_column_name='total_price_net',
                          existing_type=sa.Numeric(10, 5),
                          existing_nullable=True,
                          existing_server_default=sa.text('0.0'))
            print("SUCCESS: Renamed total_without_tax to total_price_net in orders")
        elif 'total_price_net' in columns:
            print("INFO: total_price_net column already exists in orders")


def downgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    # ==================== ORDERS ====================
    if 'orders' in inspector.get_table_names():
        columns = [col['name'] for col in inspector.get_columns('orders')]
        
        # Rinomina total_price_net -> total_without_tax
        if 'total_price_net' in columns and 'total_without_tax' not in columns:
            op.alter_column('orders', 'total_price_net',
                          new_column_name='total_without_tax',
                          existing_type=sa.Numeric(10, 5),
                          existing_nullable=True,
                          existing_server_default=sa.text('0.0'))
            print("SUCCESS: Renamed total_price_net to total_without_tax in orders")
        
        # Rinomina total_price_with_tax -> total_with_tax
        if 'total_price_with_tax' in columns and 'total_with_tax' not in columns:
            op.alter_column('orders', 'total_price_with_tax',
                          new_column_name='total_with_tax',
                          existing_type=sa.Numeric(10, 5),
                          existing_nullable=False,
                          existing_server_default=sa.text('0'))
            print("SUCCESS: Renamed total_price_with_tax to total_with_tax in orders")
        
        # Aggiungi total_price_tax_excl se non esiste
        if 'total_price_tax_excl' not in columns:
            op.add_column('orders', sa.Column('total_price_tax_excl', sa.Numeric(10, 5), nullable=True, server_default=sa.text('0')))
            print("SUCCESS: Added total_price_tax_excl column to orders")

