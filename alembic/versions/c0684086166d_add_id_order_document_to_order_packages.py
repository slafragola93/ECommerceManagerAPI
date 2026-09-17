"""add_id_order_document_to_order_packages

Revision ID: c0684086166d
Revises: f0c442dfcdd9
Create Date: 2025-10-31 15:28:52.390045

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c0684086166d'
down_revision: Union[str, None] = 'f0c442dfcdd9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Controlla se la colonna esiste già
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    # Verifica se la tabella order_packages esiste
    if 'order_packages' not in inspector.get_table_names():
        print("⚠️  order_packages table does not exist")
        return
    
    # Verifica se la colonna id_order_document esiste già
    columns = [col['name'] for col in inspector.get_columns('order_packages')]
    
    if 'id_order_document' not in columns:
        # Aggiungi colonna id_order_document
        op.add_column('order_packages',
            sa.Column('id_order_document', sa.Integer(), nullable=True)
        )
        
        # Aggiungi foreign key constraint
        try:
            op.create_foreign_key(
                'fk_order_packages_id_order_document',
                'order_packages',
                'orders_document',
                ['id_order_document'],
                ['id_order_document']
            )
        except Exception as e:
            print(f"⚠️  Could not create foreign key to orders_document: {e}")
        
        # Crea indice per migliorare le performance
        try:
            op.create_index('idx_order_packages_id_order_document', 'order_packages', ['id_order_document'])
        except Exception as e:
            print(f"⚠️  Could not create index: {e}")
        
        print("✅ Added id_order_document column to order_packages table")
    else:
        print("⚠️  id_order_document column already exists in order_packages table")


def downgrade() -> None:
    # Controlla se la colonna esiste
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    # Verifica se la tabella order_packages esiste
    if 'order_packages' not in inspector.get_table_names():
        print("⚠️  order_packages table does not exist")
        return
    
    # Verifica se la colonna id_order_document esiste
    columns = [col['name'] for col in inspector.get_columns('order_packages')]
    
    if 'id_order_document' in columns:
        # Rimuovi indice se esiste
        try:
            op.drop_index('idx_order_packages_id_order_document', table_name='order_packages')
        except Exception:
            pass  # Indice potrebbe non esistere
        
        # Rimuovi foreign key constraint se esiste
        try:
            op.drop_constraint('fk_order_packages_id_order_document', 'order_packages', type_='foreignkey')
        except Exception:
            pass  # Foreign key potrebbe non esistere
        
        # Rimuovi colonna
        op.drop_column('order_packages', 'id_order_document')
        
        print("✅ Removed id_order_document column from order_packages table")
    else:
        print("⚠️  id_order_document column does not exist in order_packages table")
