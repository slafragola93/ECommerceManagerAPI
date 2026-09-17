"""recreate_shipment_documents_table

Revision ID: 61211a674615
Revises: 243d20ef8d01
Create Date: 2025-10-24 16:49:43.130483

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '61211a674615'
down_revision: Union[str, None] = '243d20ef8d01'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Controlla se la tabella esiste già
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    tables = inspector.get_table_names()
    
    if 'shipment_documents' not in tables:
        # Crea la tabella shipment_documents
        op.create_table('shipment_documents',
            sa.Column('id', sa.Integer(), nullable=False, primary_key=True, index=True),
            sa.Column('awb', sa.String(50), nullable=False, index=True),
            sa.Column('id_shipment_request', sa.Integer(), nullable=True),
            sa.Column('order_id', sa.Integer(), nullable=True, index=True),
            sa.Column('carrier_api_id', sa.Integer(), nullable=True, index=True),
            sa.Column('type_code', sa.String(50), nullable=False),
            sa.Column('file_path', sa.String(500), nullable=False, unique=True),
            sa.Column('mime_type', sa.String(100), nullable=False),
            sa.Column('sha256_hash', sa.String(64), nullable=False, index=True),
            sa.Column('size_bytes', sa.BigInteger(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False, index=True),
            sa.Column('expires_at', sa.DateTime(), nullable=False, index=True),
        )
        
        # Aggiungi foreign key verso shipment_requests se la tabella esiste
        try:
            if 'shipment_requests' in tables:
                op.create_foreign_key('fk_shipment_documents_id_shipment_request', 'shipment_documents', 'shipment_requests', ['id_shipment_request'], ['id'])
        except Exception as e:
            print(f"⚠️  Could not create foreign key to shipment_requests: {e}")
        
        print("✅ Created shipment_documents table")
    else:
        print("⚠️  shipment_documents table already exists")


def downgrade() -> None:
    # Controlla se la tabella esiste
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    tables = inspector.get_table_names()
    
    if 'shipment_documents' in tables:
        # Rimuovi foreign key se esiste
        try:
            op.drop_constraint('fk_shipment_documents_id_shipment_request', 'shipment_documents', type_='foreignkey')
        except Exception:
            pass  # Foreign key potrebbe non esistere
        
        # Elimina la tabella
        op.drop_table('shipment_documents')
        print("✅ Dropped shipment_documents table")
    else:
        print("⚠️  shipment_documents table does not exist")
