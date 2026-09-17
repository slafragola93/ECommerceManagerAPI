"""remove_apply_discount_to_tax_included_from_order_document

Revision ID: 6ed9b7749d11
Revises: cffc95e08aee
Create Date: 2025-11-18 09:26:39.341858

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6ed9b7749d11'
down_revision: Union[str, None] = 'cffc95e08aee'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Controlla se la colonna esiste prima di rimuoverla
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    # Verifica se la tabella orders_document esiste
    if 'orders_document' not in inspector.get_table_names():
        print("WARNING: orders_document table does not exist")
        return
    
    # Verifica se la colonna esiste
    columns = [col['name'] for col in inspector.get_columns('orders_document')]
    
    # Rimuovi colonna apply_discount_to_tax_included
    if 'apply_discount_to_tax_included' in columns:
        op.drop_column('orders_document', 'apply_discount_to_tax_included')
        print("SUCCESS: Removed apply_discount_to_tax_included column from orders_document table")
    else:
        print("WARNING: apply_discount_to_tax_included column does not exist in orders_document table")


def downgrade() -> None:
    # Controlla se la colonna esiste prima di aggiungerla
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    # Verifica se la tabella orders_document esiste
    if 'orders_document' not in inspector.get_table_names():
        print("WARNING: orders_document table does not exist")
        return
    
    # Verifica se la colonna esiste già
    columns = [col['name'] for col in inspector.get_columns('orders_document')]
    
    # Aggiungi colonna apply_discount_to_tax_included (per rollback)
    if 'apply_discount_to_tax_included' not in columns:
        op.add_column('orders_document',
            sa.Column('apply_discount_to_tax_included', sa.Boolean(), nullable=True, server_default='0')
        )
        print("SUCCESS: Added apply_discount_to_tax_included column to orders_document table")
    else:
        print("WARNING: apply_discount_to_tax_included column already exists in orders_document table")
