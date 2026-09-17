"""update_price_columns_order_and_fiscal_details

Revision ID: a1b2c3d4e5f7
Revises: 4aae2ac6033d
Create Date: 2025-01-XX XX:XX:XX.XXXXXX

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f7'
down_revision: Union[str, None] = '4aae2ac6033d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    # ==================== ORDER_DETAILS ====================
    if 'order_details' in inspector.get_table_names():
        columns = [col['name'] for col in inspector.get_columns('order_details')]
        
        # Rinomina product_price -> unit_price_net
        if 'product_price' in columns and 'unit_price_net' not in columns:
            op.alter_column('order_details', 'product_price',
                          new_column_name='unit_price_net',
                          existing_type=sa.Numeric(10, 5),
                          existing_nullable=True)
            print("SUCCESS: Renamed product_price to unit_price_net in order_details")
        elif 'unit_price_net' in columns:
            print("INFO: unit_price_net already exists in order_details")
        else:
            print("WARNING: product_price column does not exist in order_details")
        
        # Aggiungi nuove colonne (nullable=True inizialmente per compatibilità)
        if 'unit_price_with_tax' not in columns:
            op.add_column('order_details',
                sa.Column('unit_price_with_tax', sa.Numeric(10, 5), nullable=True)
            )
            print("SUCCESS: Added unit_price_with_tax column to order_details")
        
        if 'total_price_net' not in columns:
            op.add_column('order_details',
                sa.Column('total_price_net', sa.Numeric(10, 5), nullable=True)
            )
            print("SUCCESS: Added total_price_net column to order_details")
        
        if 'total_price_with_tax' not in columns:
            op.add_column('order_details',
                sa.Column('total_price_with_tax', sa.Numeric(10, 5), nullable=True)
            )
            print("SUCCESS: Added total_price_with_tax column to order_details")
    
    # ==================== FISCAL_DOCUMENT_DETAILS ====================
    if 'fiscal_document_details' in inspector.get_table_names():
        columns = [col['name'] for col in inspector.get_columns('fiscal_document_details')]
        
        # Rinomina unit_price -> unit_price_net
        if 'unit_price' in columns and 'unit_price_net' not in columns:
            op.alter_column('fiscal_document_details', 'unit_price',
                          new_column_name='unit_price_net',
                          existing_type=sa.Numeric(10, 5),
                          existing_nullable=False)
            print("SUCCESS: Renamed unit_price to unit_price_net in fiscal_document_details")
        elif 'unit_price_net' in columns:
            print("INFO: unit_price_net already exists in fiscal_document_details")
        else:
            print("WARNING: unit_price column does not exist in fiscal_document_details")
        
        # Aggiungi nuove colonne (nullable=True inizialmente per compatibilità)
        if 'unit_price_with_tax' not in columns:
            op.add_column('fiscal_document_details',
                sa.Column('unit_price_with_tax', sa.Numeric(10, 5), nullable=True)
            )
            print("SUCCESS: Added unit_price_with_tax column to fiscal_document_details")
        
        if 'total_price_net' not in columns:
            op.add_column('fiscal_document_details',
                sa.Column('total_price_net', sa.Numeric(10, 5), nullable=True)
            )
            print("SUCCESS: Added total_price_net column to fiscal_document_details")
        
        if 'total_price_with_tax' not in columns:
            op.add_column('fiscal_document_details',
                sa.Column('total_price_with_tax', sa.Numeric(10, 5), nullable=True)
            )
            print("SUCCESS: Added total_price_with_tax column to fiscal_document_details")
        
        # Nota: total_amount viene mantenuto per retrocompatibilità
        # e sarà sincronizzato con total_price_with_tax


def downgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    # ==================== ORDER_DETAILS ====================
    if 'order_details' in inspector.get_table_names():
        columns = [col['name'] for col in inspector.get_columns('order_details')]
        
        # Rimuovi nuove colonne
        if 'total_price_with_tax' in columns:
            op.drop_column('order_details', 'total_price_with_tax')
            print("SUCCESS: Removed total_price_with_tax column from order_details")
        
        if 'total_price_net' in columns:
            op.drop_column('order_details', 'total_price_net')
            print("SUCCESS: Removed total_price_net column from order_details")
        
        if 'unit_price_with_tax' in columns:
            op.drop_column('order_details', 'unit_price_with_tax')
            print("SUCCESS: Removed unit_price_with_tax column from order_details")
        
        # Rinomina unit_price_net -> product_price
        if 'unit_price_net' in columns and 'product_price' not in columns:
            op.alter_column('order_details', 'unit_price_net',
                          new_column_name='product_price',
                          existing_type=sa.Numeric(10, 5),
                          existing_nullable=True)
            print("SUCCESS: Renamed unit_price_net to product_price in order_details")
    
    # ==================== FISCAL_DOCUMENT_DETAILS ====================
    if 'fiscal_document_details' in inspector.get_table_names():
        columns = [col['name'] for col in inspector.get_columns('fiscal_document_details')]
        
        # Rimuovi nuove colonne
        if 'total_price_with_tax' in columns:
            op.drop_column('fiscal_document_details', 'total_price_with_tax')
            print("SUCCESS: Removed total_price_with_tax column from fiscal_document_details")
        
        if 'total_price_net' in columns:
            op.drop_column('fiscal_document_details', 'total_price_net')
            print("SUCCESS: Removed total_price_net column from fiscal_document_details")
        
        if 'unit_price_with_tax' in columns:
            op.drop_column('fiscal_document_details', 'unit_price_with_tax')
            print("SUCCESS: Removed unit_price_with_tax column from fiscal_document_details")
        
        # Rinomina unit_price_net -> unit_price
        if 'unit_price_net' in columns and 'unit_price' not in columns:
            op.alter_column('fiscal_document_details', 'unit_price_net',
                          new_column_name='unit_price',
                          existing_type=sa.Numeric(10, 5),
                          existing_nullable=False)
            print("SUCCESS: Renamed unit_price_net to unit_price in fiscal_document_details")

