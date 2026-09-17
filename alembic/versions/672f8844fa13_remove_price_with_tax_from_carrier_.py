"""remove_price_with_tax_from_carrier_assignments

Revision ID: 672f8844fa13
Revises: f02884442e61
Create Date: 2025-11-28 12:00:04.320157

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '672f8844fa13'
down_revision: Union[str, None] = 'f02884442e61'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Rimuove la colonna price_with_tax dalla tabella carrier_assignments."""
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


def downgrade() -> None:
    """Ripristina la colonna price_with_tax nella tabella carrier_assignments."""
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
