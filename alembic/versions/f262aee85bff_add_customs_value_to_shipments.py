"""add_customs_value_to_shipments

Revision ID: f262aee85bff
Revises: ae595f42fb39
Create Date: 2025-11-21 08:49:52.629554

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f262aee85bff'
down_revision: Union[str, None] = 'ae595f42fb39'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Controlla se la colonna esiste già
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    # Verifica se la tabella shipments esiste
    if 'shipments' not in inspector.get_table_names():
        print("WARNING: shipments table does not exist")
        return
    
    # Verifica se la colonna esiste già
    columns = [col['name'] for col in inspector.get_columns('shipments')]
    
    # Aggiungi colonna customs_value
    if 'customs_value' not in columns:
        op.add_column('shipments',
            sa.Column('customs_value', sa.Numeric(10, 5), nullable=True)
        )
        print("SUCCESS: Added customs_value column to shipments table")
    else:
        print("WARNING: customs_value column already exists in shipments table")


def downgrade() -> None:
    # Controlla se la colonna esiste
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    # Verifica se la tabella shipments esiste
    if 'shipments' not in inspector.get_table_names():
        print("WARNING: shipments table does not exist")
        return
    
    # Verifica se la colonna esiste
    columns = [col['name'] for col in inspector.get_columns('shipments')]
    
    # Rimuovi colonna customs_value
    if 'customs_value' in columns:
        op.drop_column('shipments', 'customs_value')
        print("SUCCESS: Removed customs_value column from shipments table")
    else:
        print("WARNING: customs_value column does not exist in shipments table")
