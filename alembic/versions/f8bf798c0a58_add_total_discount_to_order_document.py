"""add_total_discount_to_order_document

Revision ID: f8bf798c0a58
Revises: 2f5fefbe9555
Create Date: 2025-01-27 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f8bf798c0a58'
down_revision: Union[str, None] = '2f5fefbe9555'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Controlla se le colonne esistono già
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    # Verifica se la tabella orders_document esiste
    if 'orders_document' not in inspector.get_table_names():
        print("WARNING: orders_document table does not exist")
        return
    
    # Verifica se le colonne esistono già
    columns = [col['name'] for col in inspector.get_columns('orders_document')]
    
    # Aggiungi colonna total_discount
    if 'total_discount' not in columns:
        op.add_column('orders_document',
            sa.Column('total_discount', sa.Float(), nullable=True, server_default='0.0')
        )
        print("SUCCESS: Added total_discount column to orders_document table")
    else:
        print("WARNING: total_discount column already exists in orders_document table")
    
    # Aggiungi colonna apply_discount_to_tax_included
    if 'apply_discount_to_tax_included' not in columns:
        op.add_column('orders_document',
            sa.Column('apply_discount_to_tax_included', sa.Boolean(), nullable=True, server_default='0')
        )
        print("SUCCESS: Added apply_discount_to_tax_included column to orders_document table")
    else:
        print("WARNING: apply_discount_to_tax_included column already exists in orders_document table")


def downgrade() -> None:
    # Controlla se le colonne esistono
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    # Verifica se la tabella orders_document esiste
    if 'orders_document' not in inspector.get_table_names():
        print("WARNING: orders_document table does not exist")
        return
    
    # Verifica se le colonne esistono
    columns = [col['name'] for col in inspector.get_columns('orders_document')]
    
    # Rimuovi colonna apply_discount_to_tax_included
    if 'apply_discount_to_tax_included' in columns:
        op.drop_column('orders_document', 'apply_discount_to_tax_included')
        print("SUCCESS: Removed apply_discount_to_tax_included column from orders_document table")
    else:
        print("WARNING: apply_discount_to_tax_included column does not exist in orders_document table")
    
    # Rimuovi colonna total_discount
    if 'total_discount' in columns:
        op.drop_column('orders_document', 'total_discount')
        print("SUCCESS: Removed total_discount column from orders_document table")
    else:
        print("WARNING: total_discount column does not exist in orders_document table")

