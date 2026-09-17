"""add_total_price_net_to_order_document

Revision ID: eece980240d4
Revises: d4e5f6a7b8c9
Create Date: 2025-01-27 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'eece980240d4'
down_revision: Union[str, None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Controlla se la colonna esiste già
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    # Verifica se la tabella orders_document esiste
    if 'orders_document' not in inspector.get_table_names():
        print("WARNING: orders_document table does not exist")
        return
    
    # Verifica se la colonna esiste già
    columns = [col['name'] for col in inspector.get_columns('orders_document')]
    
    # Aggiungi colonna total_price_net
    if 'total_price_net' not in columns:
        op.add_column('orders_document',
            sa.Column('total_price_net', sa.Numeric(10, 5), nullable=True, server_default='0.0')
        )
        print("SUCCESS: Added total_price_net column to orders_document table")
    else:
        print("WARNING: total_price_net column already exists in orders_document table")


def downgrade() -> None:
    # Controlla se la colonna esiste
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    # Verifica se la tabella orders_document esiste
    if 'orders_document' not in inspector.get_table_names():
        print("WARNING: orders_document table does not exist")
        return
    
    # Verifica se la colonna esiste
    columns = [col['name'] for col in inspector.get_columns('orders_document')]
    
    # Rimuovi colonna total_price_net
    if 'total_price_net' in columns:
        op.drop_column('orders_document', 'total_price_net')
        print("SUCCESS: Removed total_price_net column from orders_document table")
    else:
        print("WARNING: total_price_net column does not exist in orders_document table")

