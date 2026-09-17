"""remove_default_price_no_tax_and_id_tax_from_carriers_api

Revision ID: 4aae2ac6033d
Revises: f262aee85bff
Create Date: 2025-11-21 16:14:10.936878

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4aae2ac6033d'
down_revision: Union[str, None] = 'f262aee85bff'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Controlla se le colonne esistono
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    # Verifica se la tabella carriers_api esiste
    if 'carriers_api' not in inspector.get_table_names():
        print("WARNING: carriers_api table does not exist")
        return
    
    # Verifica se le colonne esistono
    columns = [col['name'] for col in inspector.get_columns('carriers_api')]
    
    # Rimuovi foreign key constraint se esiste
    if 'id_tax' in columns:
        try:
            op.drop_constraint('fk_carriers_api_id_tax', 'carriers_api', type_='foreignkey')
            print("SUCCESS: Removed foreign key constraint fk_carriers_api_id_tax")
        except Exception as e:
            print(f"WARNING: Could not remove foreign key constraint: {e}")
    
    # Rimuovi colonna id_tax
    if 'id_tax' in columns:
        op.drop_column('carriers_api', 'id_tax')
        print("SUCCESS: Removed id_tax column from carriers_api table")
    else:
        print("WARNING: id_tax column does not exist in carriers_api table")
    
    # Rimuovi colonna default_price_no_tax
    if 'default_price_no_tax' in columns:
        op.drop_column('carriers_api', 'default_price_no_tax')
        print("SUCCESS: Removed default_price_no_tax column from carriers_api table")
    else:
        print("WARNING: default_price_no_tax column does not exist in carriers_api table")


def downgrade() -> None:
    # Controlla se le colonne esistono già
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    # Verifica se la tabella carriers_api esiste
    if 'carriers_api' not in inspector.get_table_names():
        print("WARNING: carriers_api table does not exist")
        return
    
    # Verifica se le colonne esistono già
    columns = [col['name'] for col in inspector.get_columns('carriers_api')]
    
    # Aggiungi colonna default_price_no_tax
    if 'default_price_no_tax' not in columns:
        op.add_column('carriers_api',
            sa.Column('default_price_no_tax', sa.Numeric(10, 5), nullable=False, server_default=sa.text('0.0'))
        )
        print("SUCCESS: Added default_price_no_tax column to carriers_api table")
    else:
        print("WARNING: default_price_no_tax column already exists in carriers_api table")
    
    # Aggiungi colonna id_tax
    if 'id_tax' not in columns:
        op.add_column('carriers_api',
            sa.Column('id_tax', sa.Integer(), nullable=False, server_default=sa.text('1'))
        )
        # Aggiungi foreign key constraint
        op.create_foreign_key(
            'fk_carriers_api_id_tax',
            'carriers_api', 'taxes',
            ['id_tax'], ['id_tax']
        )
        print("SUCCESS: Added id_tax column to carriers_api table")
    else:
        print("WARNING: id_tax column already exists in carriers_api table")
