"""remove_shipment_requests_table_and_column

Revision ID: 4b958b35bac0
Revises: 216412b7036b
Create Date: 2025-11-05 09:08:22.990993

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4b958b35bac0'
down_revision: Union[str, None] = '216412b7036b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Rimuove la tabella shipment_requests e la colonna id_shipment_request da shipment_documents.
    Questo elimina completamente il sistema di audit delle richieste di spedizione.
    """
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    # Verifica se le tabelle/colonne esistono prima di rimuoverle
    tables = inspector.get_table_names()
    columns = {}
    
    if 'shipment_documents' in tables:
        columns = {col['name']: col for col in inspector.get_columns('shipment_documents')}
    
    # Step 1: Rimuovi la foreign key da shipment_documents se esiste
    if 'shipment_documents' in tables:
        # Prova diversi nomi possibili per la foreign key
        foreign_keys = inspector.get_foreign_keys('shipment_documents')
        for fk in foreign_keys:
            if 'id_shipment_request' in fk.get('constrained_columns', []):
                fk_name = fk['name']
                try:
                    op.drop_constraint(fk_name, 'shipment_documents', type_='foreignkey')
                    print(f"✅ Dropped foreign key {fk_name} from shipment_documents")
                except Exception as e:
                    print(f"⚠️  Could not drop foreign key {fk_name}: {e}")
        
        # Prova anche il nome standard che potrebbe essere stato creato
        try:
            op.drop_constraint('fk_shipment_documents_id_shipment_request', 'shipment_documents', type_='foreignkey')
            print("✅ Dropped foreign key fk_shipment_documents_id_shipment_request")
        except Exception:
            pass  # Foreign key potrebbe non esistere con questo nome
    
    # Step 2: Rimuovi la colonna id_shipment_request da shipment_documents
    if 'shipment_documents' in tables and 'id_shipment_request' in columns:
        op.drop_column('shipment_documents', 'id_shipment_request')
        print("✅ Dropped column id_shipment_request from shipment_documents")
    else:
        print("⚠️  Column id_shipment_request not found in shipment_documents, skipping")
    
    # Step 3: Rimuovi la tabella shipment_requests
    if 'shipment_requests' in tables:
        # Rimuovi gli indici prima di eliminare la tabella
        try:
            op.drop_index('ix_shipment_requests_message_reference', table_name='shipment_requests')
        except Exception:
            pass
        try:
            op.drop_index('ix_shipment_requests_id', table_name='shipment_requests')
        except Exception:
            pass
        try:
            op.drop_index('ix_shipment_requests_expires_at', table_name='shipment_requests')
        except Exception:
            pass
        try:
            op.drop_index('ix_shipment_requests_awb', table_name='shipment_requests')
        except Exception:
            pass
        
        op.drop_table('shipment_requests')
        print("✅ Dropped table shipment_requests")
    else:
        print("⚠️  Table shipment_requests not found, skipping")
    
    print("✅ Migration completed: removed shipment_requests table and id_shipment_request column")


def downgrade() -> None:
    """
    Ripristina la tabella shipment_requests e la colonna id_shipment_request in shipment_documents.
    """
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    tables = inspector.get_table_names()
    
    # Step 1: Ricrea la tabella shipment_requests
    if 'shipment_requests' not in tables:
        op.create_table('shipment_requests',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('id_order', sa.Integer(), nullable=False),
            sa.Column('id_carrier_api', sa.Integer(), nullable=False),
            sa.Column('awb', sa.String(length=50), nullable=True),
            sa.Column('message_reference', sa.String(length=100), nullable=True),
            sa.Column('request_json_redacted', sa.Text(), nullable=True),
            sa.Column('response_json_redacted', sa.Text(), nullable=True),
            sa.Column('environment', sa.Enum('SANDBOX', 'PRODUCTION', name='environmentenum'), nullable=False),
            sa.Column('status_code', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('expires_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['id_carrier_api'], ['carriers_api.id_carrier_api'], ),
            sa.ForeignKeyConstraint(['id_order'], ['orders.id_order'], ),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_shipment_requests_awb', 'shipment_requests', ['awb'], unique=False)
        op.create_index('ix_shipment_requests_expires_at', 'shipment_requests', ['expires_at'], unique=False)
        op.create_index('ix_shipment_requests_id', 'shipment_requests', ['id'], unique=False)
        op.create_index('ix_shipment_requests_message_reference', 'shipment_requests', ['message_reference'], unique=True)
        print("✅ Recreated table shipment_requests")
    
    # Step 2: Aggiungi la colonna id_shipment_request a shipment_documents
    if 'shipment_documents' in tables:
        columns = {col['name']: col for col in inspector.get_columns('shipment_documents')}
        if 'id_shipment_request' not in columns:
            op.add_column('shipment_documents', sa.Column('id_shipment_request', sa.Integer(), nullable=True))
            print("✅ Added column id_shipment_request to shipment_documents")
            
            # Ricrea la foreign key
            try:
                op.create_foreign_key(
                    'fk_shipment_documents_id_shipment_request',
                    'shipment_documents',
                    'shipment_requests',
                    ['id_shipment_request'],
                    ['id']
                )
                print("✅ Recreated foreign key fk_shipment_documents_id_shipment_request")
            except Exception as e:
                print(f"⚠️  Could not create foreign key: {e}")
    
    print("✅ Downgrade completed: restored shipment_requests table and id_shipment_request column")
