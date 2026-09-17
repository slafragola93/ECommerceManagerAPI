"""recreate_order_document_table

Revision ID: 243d20ef8d01
Revises: 9f3eb3459e01
Create Date: 2025-10-24 16:48:56.645901

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '243d20ef8d01'
down_revision: Union[str, None] = '9f3eb3459e01'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Controlla se la tabella esiste già
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    tables = inspector.get_table_names()
    
    if 'orders_document' not in tables:
        # Crea la tabella orders_document
        op.create_table('orders_document',
            sa.Column('id_order_document', sa.Integer(), nullable=False, primary_key=True, index=True),
            sa.Column('id_order', sa.Integer(), nullable=True, index=True),
            sa.Column('id_address_delivery', sa.Integer(), nullable=True, index=True),
            sa.Column('id_address_invoice', sa.Integer(), nullable=True, index=True),
            sa.Column('id_customer', sa.Integer(), nullable=True, index=True),
            sa.Column('id_sectional', sa.Integer(), nullable=True, index=True),
            sa.Column('id_shipping', sa.Integer(), nullable=True, index=True),
            sa.Column('document_number', sa.String(32), nullable=True),
            sa.Column('type_document', sa.String(32), nullable=True),
            sa.Column('total_weight', sa.Float(), nullable=True),
            sa.Column('total_price_with_tax', sa.Float(), nullable=True),
            sa.Column('is_invoice_requested', sa.Boolean(), nullable=True, default=False),
            sa.Column('note', sa.String(200), nullable=True),
            sa.Column('date_add', sa.Date(), nullable=True, default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=True, default=sa.func.now(), onupdate=sa.func.now()),
        )
        
        # Aggiungi foreign keys
        op.create_foreign_key('fk_orders_document_id_order', 'orders_document', 'orders', ['id_order'], ['id_order'])
        op.create_foreign_key('fk_orders_document_id_address_delivery', 'orders_document', 'addresses', ['id_address_delivery'], ['id_address'])
        op.create_foreign_key('fk_orders_document_id_address_invoice', 'orders_document', 'addresses', ['id_address_invoice'], ['id_address'])
        op.create_foreign_key('fk_orders_document_id_customer', 'orders_document', 'customers', ['id_customer'], ['id_customer'])
        op.create_foreign_key('fk_orders_document_id_sectional', 'orders_document', 'sectionals', ['id_sectional'], ['id_sectional'])
        op.create_foreign_key('fk_orders_document_id_shipping', 'orders_document', 'shipments', ['id_shipping'], ['id_shipping'])
        
        print("✅ Created orders_document table")
    else:
        print("⚠️  orders_document table already exists")


def downgrade() -> None:
    # Controlla se la tabella esiste
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    tables = inspector.get_table_names()
    
    if 'orders_document' in tables:
        # Rimuovi foreign keys prima di eliminare la tabella
        op.drop_constraint('fk_orders_document_id_order', 'orders_document', type_='foreignkey')
        op.drop_constraint('fk_orders_document_id_address_delivery', 'orders_document', type_='foreignkey')
        op.drop_constraint('fk_orders_document_id_address_invoice', 'orders_document', type_='foreignkey')
        op.drop_constraint('fk_orders_document_id_customer', 'orders_document', type_='foreignkey')
        op.drop_constraint('fk_orders_document_id_sectional', 'orders_document', type_='foreignkey')
        op.drop_constraint('fk_orders_document_id_shipping', 'orders_document', type_='foreignkey')
        
        # Elimina la tabella
        op.drop_table('orders_document')
        print("✅ Dropped orders_document table")
    else:
        print("⚠️  orders_document table does not exist")
