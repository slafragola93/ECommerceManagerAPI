"""add_id_payment_to_order_document

Revision ID: f0c442dfcdd9
Revises: 61211a674615
Create Date: 2025-10-31 11:39:32.620573

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f0c442dfcdd9'
down_revision: Union[str, None] = '61211a674615'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Controlla se la colonna esiste già
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    # Verifica se la tabella orders_document esiste
    if 'orders_document' not in inspector.get_table_names():
        print("⚠️  orders_document table does not exist")
        return
    
    # Verifica se la colonna id_payment esiste già
    columns = [col['name'] for col in inspector.get_columns('orders_document')]
    
    if 'id_payment' not in columns:
        # Aggiungi colonna id_payment
        op.add_column('orders_document',
            sa.Column('id_payment', sa.Integer(), nullable=True)
        )
        
        # Aggiungi foreign key constraint
        try:
            op.create_foreign_key(
                'fk_orders_document_id_payment',
                'orders_document',
                'payments',
                ['id_payment'],
                ['id_payment']
            )
        except Exception as e:
            print(f"⚠️  Could not create foreign key to payments: {e}")
        
        # Crea indice per migliorare le performance
        try:
            op.create_index('idx_orders_document_id_payment', 'orders_document', ['id_payment'])
        except Exception as e:
            print(f"⚠️  Could not create index: {e}")
        
        print("✅ Added id_payment column to orders_document table")
    else:
        print("⚠️  id_payment column already exists in orders_document table")


def downgrade() -> None:
    # Controlla se la colonna esiste
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    # Verifica se la tabella orders_document esiste
    if 'orders_document' not in inspector.get_table_names():
        print("⚠️  orders_document table does not exist")
        return
    
    # Verifica se la colonna id_payment esiste
    columns = [col['name'] for col in inspector.get_columns('orders_document')]
    
    if 'id_payment' in columns:
        # Rimuovi indice se esiste
        try:
            op.drop_index('idx_orders_document_id_payment', table_name='orders_document')
        except Exception:
            pass  # Indice potrebbe non esistere
        
        # Rimuovi foreign key constraint se esiste
        try:
            op.drop_constraint('fk_orders_document_id_payment', 'orders_document', type_='foreignkey')
        except Exception:
            pass  # Foreign key potrebbe non esistere
        
        # Rimuovi colonna
        op.drop_column('orders_document', 'id_payment')
        
        print("✅ Removed id_payment column from orders_document table")
    else:
        print("⚠️  id_payment column does not exist in orders_document table")
