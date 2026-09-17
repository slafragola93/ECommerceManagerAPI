"""rename_total_paid_to_total_with_tax

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2025-01-XX XX:XX:XX.XXXXXX

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    # ==================== ORDERS ====================
    if 'orders' in inspector.get_table_names():
        columns = [col['name'] for col in inspector.get_columns('orders')]
        
        # Rinomina total_paid -> total_with_tax
        if 'total_paid' in columns and 'total_with_tax' not in columns:
            op.alter_column('orders', 'total_paid',
                          new_column_name='total_with_tax',
                          existing_type=sa.Numeric(10, 5),
                          existing_nullable=False,
                          existing_server_default=sa.text('0'))
            print("SUCCESS: Renamed total_paid to total_with_tax in orders")
        elif 'total_with_tax' in columns:
            print("INFO: total_with_tax column already exists in orders")
        
        # Aggiungi total_without_tax se non esiste
        if 'total_without_tax' not in columns:
            op.add_column('orders', sa.Column('total_without_tax', sa.Numeric(10, 5), nullable=True, server_default=sa.text('0.0')))
            print("SUCCESS: Added total_without_tax column to orders")
            
            # Calcola total_without_tax dai dati esistenti usando percentuale IVA default 22%
            # total_without_tax = total_with_tax / (1 + 0.22)
            op.execute("""
                UPDATE orders 
                SET total_without_tax = total_with_tax / 1.22 
                WHERE total_with_tax > 0
            """)
            print("SUCCESS: Calculated total_without_tax from existing total_with_tax data (using 22% default tax)")
        else:
            print("INFO: total_without_tax column already exists in orders")


def downgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    # ==================== ORDERS ====================
    if 'orders' in inspector.get_table_names():
        columns = [col['name'] for col in inspector.get_columns('orders')]
        
        # Rimuovi total_without_tax se esiste
        if 'total_without_tax' in columns:
            op.drop_column('orders', 'total_without_tax')
            print("SUCCESS: Dropped total_without_tax column from orders")
        
        # Rinomina total_with_tax -> total_paid
        if 'total_with_tax' in columns and 'total_paid' not in columns:
            op.alter_column('orders', 'total_with_tax',
                          new_column_name='total_paid',
                          existing_type=sa.Numeric(10, 5),
                          existing_nullable=False,
                          existing_server_default=sa.text('0'))
            print("SUCCESS: Renamed total_with_tax to total_paid in orders")

