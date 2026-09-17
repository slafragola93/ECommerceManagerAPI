"""add_price_with_tax_to_carrier_assignments

Revision ID: 76a0ebef4812
Revises: eece980240d4
Create Date: 2025-11-28 10:14:26.391686

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '76a0ebef4812'
down_revision: Union[str, None] = 'eece980240d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Controlla se la colonna esiste già
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    # Verifica se la tabella carrier_assignments esiste
    if 'carrier_assignments' not in inspector.get_table_names():
        print("WARNING: carrier_assignments table does not exist")
        return
    
    # Verifica se la colonna esiste già
    columns = [col['name'] for col in inspector.get_columns('carrier_assignments')]
    
    # Aggiungi colonna price_with_tax
    if 'price_with_tax' not in columns:
        op.add_column('carrier_assignments',
            sa.Column('price_with_tax', sa.Numeric(10, 5), nullable=True)
        )
        print("SUCCESS: Added price_with_tax column to carrier_assignments table")
    else:
        print("WARNING: price_with_tax column already exists in carrier_assignments table")


def downgrade() -> None:
    # Controlla se la colonna esiste
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    # Verifica se la tabella carrier_assignments esiste
    if 'carrier_assignments' not in inspector.get_table_names():
        print("WARNING: carrier_assignments table does not exist")
        return
    
    # Verifica se la colonna esiste
    columns = [col['name'] for col in inspector.get_columns('carrier_assignments')]
    
    # Rimuovi colonna price_with_tax
    if 'price_with_tax' in columns:
        op.drop_column('carrier_assignments', 'price_with_tax')
        print("SUCCESS: Removed price_with_tax column from carrier_assignments table")
    else:
        print("WARNING: price_with_tax column does not exist in carrier_assignments table")
