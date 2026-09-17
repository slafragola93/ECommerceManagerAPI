"""add_id_store_to_payments

Revision ID: ad34c0277fad
Revises: 5cdce791402d
Create Date: 2026-01-27 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ad34c0277fad'
down_revision: Union[str, None] = '5cdce791402d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    # Verifica se la colonna esiste già
    result = connection.execute(sa.text("""
        SELECT COUNT(*) as count 
        FROM information_schema.COLUMNS 
        WHERE TABLE_SCHEMA = DATABASE() 
        AND TABLE_NAME = 'payments' 
        AND COLUMN_NAME = 'id_store'
    """))
    column_exists = result.fetchone()[0] > 0
    
    if not column_exists:
        # Aggiungi colonna id_store alla tabella payments (nullable=True come specificato)
        op.add_column('payments', sa.Column('id_store', sa.Integer(), nullable=True))
    
    # Verifica se la foreign key esiste già
    result = connection.execute(sa.text("""
        SELECT COUNT(*) as count 
        FROM information_schema.KEY_COLUMN_USAGE 
        WHERE TABLE_SCHEMA = DATABASE() 
        AND TABLE_NAME = 'payments' 
        AND CONSTRAINT_NAME = 'fk_payments_store'
    """))
    fk_exists = result.fetchone()[0] > 0
    
    if not fk_exists:
        # Crea foreign key
        op.create_foreign_key(
            'fk_payments_store',
            'payments',
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
        AND TABLE_NAME = 'payments' 
        AND INDEX_NAME = 'ix_payments_id_store'
    """))
    index_exists = result.fetchone()[0] > 0
    
    if not index_exists:
        # Crea indice
        op.create_index(
            op.f('ix_payments_id_store'),
            'payments',
            ['id_store'],
            unique=False
        )


def downgrade() -> None:
    # Rimuovi indice
    op.drop_index(op.f('ix_payments_id_store'), table_name='payments')
    
    # Rimuovi foreign key
    op.drop_constraint('fk_payments_store', 'payments', type_='foreignkey')
    
    # Rimuovi colonna
    op.drop_column('payments', 'id_store')
