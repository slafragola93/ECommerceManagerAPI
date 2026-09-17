"""add_note_to_order_detail

Revision ID: 150bf63bde32
Revises: f8bf798c0a58
Create Date: 2025-11-06 12:18:27.209349

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '150bf63bde32'
down_revision: Union[str, None] = 'f8bf798c0a58'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Controlla se la colonna esiste già
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    # Verifica se la tabella order_details esiste
    if 'order_details' not in inspector.get_table_names():
        print("WARNING: order_details table does not exist")
        return
    
    # Verifica se la colonna esiste già
    columns = [col['name'] for col in inspector.get_columns('order_details')]
    
    # Aggiungi colonna note
    if 'note' not in columns:
        op.add_column('order_details',
            sa.Column('note', sa.String(200), nullable=True)
        )
        print("SUCCESS: Added note column to order_details table")
    else:
        print("WARNING: note column already exists in order_details table")


def downgrade() -> None:
    # Controlla se la colonna esiste
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    # Verifica se la tabella order_details esiste
    if 'order_details' not in inspector.get_table_names():
        print("WARNING: order_details table does not exist")
        return
    
    # Verifica se la colonna esiste
    columns = [col['name'] for col in inspector.get_columns('order_details')]
    
    # Rimuovi colonna note
    if 'note' in columns:
        op.drop_column('order_details', 'note')
        print("SUCCESS: Removed note column from order_details table")
    else:
        print("WARNING: note column does not exist in order_details table")
