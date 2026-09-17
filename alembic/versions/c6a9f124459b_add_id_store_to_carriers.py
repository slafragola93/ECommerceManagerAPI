"""add_id_store_to_carriers

Revision ID: c6a9f124459b
Revises: ed8f92f38a64
Create Date: 2025-01-27 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c6a9f124459b'
down_revision: Union[str, None] = 'ed8f92f38a64'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()
    
    # Verifica se la colonna esiste già
    result = connection.execute(sa.text("""
        SELECT COUNT(*) as count 
        FROM information_schema.COLUMNS 
        WHERE TABLE_SCHEMA = DATABASE() 
        AND TABLE_NAME = 'carriers' 
        AND COLUMN_NAME = 'id_store'
    """))
    column_exists = result.fetchone()[0] > 0
    
    if not column_exists:
        # Aggiungi colonna id_store alla tabella carriers (nullable=True come specificato)
        op.add_column('carriers', sa.Column('id_store', sa.Integer(), nullable=True))
    
    # Verifica se la foreign key esiste già
    result = connection.execute(sa.text("""
        SELECT COUNT(*) as count 
        FROM information_schema.KEY_COLUMN_USAGE 
        WHERE TABLE_SCHEMA = DATABASE() 
        AND TABLE_NAME = 'carriers' 
        AND CONSTRAINT_NAME = 'fk_carriers_store'
    """))
    fk_exists = result.fetchone()[0] > 0
    
    if not fk_exists:
        # Crea foreign key
        op.create_foreign_key(
            'fk_carriers_store',
            'carriers',
            'stores',
            ['id_store'],
            ['id_store'],
            ondelete='SET NULL'
        )
    
    # Verifica se l'indice esiste già
    result = connection.execute(sa.text("""
        SELECT COUNT(*) as count 
        FROM information_schema.STATISTICS 
        WHERE TABLE_SCHEMA = DATABASE() 
        AND TABLE_NAME = 'carriers' 
        AND INDEX_NAME = 'ix_carriers_id_store'
    """))
    index_exists = result.fetchone()[0] > 0
    
    if not index_exists:
        # Crea indice
        op.create_index(
            op.f('ix_carriers_id_store'),
            'carriers',
            ['id_store'],
            unique=False
        )


def downgrade() -> None:
    # Rimuovi indice
    op.drop_index(op.f('ix_carriers_id_store'), table_name='carriers')
    
    # Rimuovi foreign key
    op.drop_constraint('fk_carriers_store', 'carriers', type_='foreignkey')
    
    # Rimuovi colonna
    op.drop_column('carriers', 'id_store')
