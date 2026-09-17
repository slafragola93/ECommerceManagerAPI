"""rename_price_without_tax_to_price

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f7
Create Date: 2025-01-XX XX:XX:XX.XXXXXX

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    # ==================== PRODUCTS ====================
    if 'products' in inspector.get_table_names():
        columns = [col['name'] for col in inspector.get_columns('products')]
        
        # Rinomina price_without_tax -> price
        if 'price_without_tax' in columns and 'price' not in columns:
            op.alter_column('products', 'price_without_tax',
                          new_column_name='price',
                          existing_type=sa.Numeric(10, 5),
                          existing_nullable=True,
                          existing_server_default=sa.text('0.0'))
            print("SUCCESS: Renamed price_without_tax to price in products")
        elif 'price' in columns:
            print("INFO: price column already exists in products")
        else:
            print("WARNING: price_without_tax column does not exist in products")


def downgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    # ==================== PRODUCTS ====================
    if 'products' in inspector.get_table_names():
        columns = [col['name'] for col in inspector.get_columns('products')]
        
        # Rinomina price -> price_without_tax
        if 'price' in columns and 'price_without_tax' not in columns:
            op.alter_column('products', 'price',
                          new_column_name='price_without_tax',
                          existing_type=sa.Numeric(10, 5),
                          existing_nullable=True,
                          existing_server_default=sa.text('0.0'))
            print("SUCCESS: Renamed price to price_without_tax in products")

