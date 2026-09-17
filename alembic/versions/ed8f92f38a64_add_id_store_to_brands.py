"""add_id_store_to_brands

Revision ID: ed8f92f38a64
Revises: 907004240072
Create Date: 2025-12-15 12:11:55.645645

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ed8f92f38a64'
down_revision: Union[str, None] = '907004240072'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()
    
    # Verifica se la colonna esiste già
    result = connection.execute(sa.text("""
        SELECT COUNT(*) as count 
        FROM information_schema.COLUMNS 
        WHERE TABLE_SCHEMA = DATABASE() 
        AND TABLE_NAME = 'brands' 
        AND COLUMN_NAME = 'id_store'
    """))
    column_exists = result.fetchone()[0] > 0
    
    if not column_exists:
        # Aggiungi colonna id_store alla tabella brands (prima nullable per aggiornare i valori)
        op.add_column('brands', sa.Column('id_store', sa.Integer(), nullable=True))
        
        # Aggiorna i record esistenti: usa id_store=1 (store di default) se esiste, altrimenti il primo store disponibile
        result = connection.execute(sa.text("SELECT id_store FROM stores WHERE id_store = 1 LIMIT 1"))
        default_store_id = result.fetchone()
        
        if default_store_id:
            default_id = 1
        else:
            # Se non esiste id_store=1, usa il primo store disponibile
            result = connection.execute(sa.text("SELECT id_store FROM stores ORDER BY id_store LIMIT 1"))
            first_store = result.fetchone()
            default_id = first_store[0] if first_store else 1
        
        # Aggiorna tutti i record con il default_id
        op.execute(sa.text(f"UPDATE brands SET id_store = {default_id} WHERE id_store IS NULL"))
        
        # Ora rendi la colonna NOT NULL
        op.alter_column('brands', 'id_store', nullable=False, server_default=str(default_id))
    
    # Verifica se la foreign key esiste già
    result = connection.execute(sa.text("""
        SELECT COUNT(*) as count 
        FROM information_schema.KEY_COLUMN_USAGE 
        WHERE TABLE_SCHEMA = DATABASE() 
        AND TABLE_NAME = 'brands' 
        AND CONSTRAINT_NAME = 'fk_brands_store'
    """))
    fk_exists = result.fetchone()[0] > 0
    
    if not fk_exists:
        # Prima aggiorna tutti i record con id_store non validi
        # Trova il primo store valido
        result = connection.execute(sa.text("SELECT id_store FROM stores ORDER BY id_store LIMIT 1"))
        first_store = result.fetchone()
        default_id = first_store[0] if first_store else 1
        
        # Aggiorna tutti i record brands con id_store che non esiste in stores
        op.execute(sa.text(f"""
            UPDATE brands b
            LEFT JOIN stores s ON b.id_store = s.id_store
            SET b.id_store = {default_id}
            WHERE s.id_store IS NULL OR b.id_store IS NULL
        """))
        
        # Crea foreign key
        op.create_foreign_key(
            'fk_brands_store',
            'brands',
            'stores',
            ['id_store'],
            ['id_store'],
            ondelete='RESTRICT'
        )
    
    # Verifica se l'indice esiste già
    result = connection.execute(sa.text("""
        SELECT COUNT(*) as count 
        FROM information_schema.STATISTICS 
        WHERE TABLE_SCHEMA = DATABASE() 
        AND TABLE_NAME = 'brands' 
        AND INDEX_NAME = 'ix_brands_id_store'
    """))
    index_exists = result.fetchone()[0] > 0
    
    if not index_exists:
        # Crea indice
        op.create_index(
            op.f('ix_brands_id_store'),
            'brands',
            ['id_store'],
            unique=False
        )


def downgrade() -> None:
    # Rimuovi indice
    op.drop_index(op.f('ix_brands_id_store'), table_name='brands')
    
    # Rimuovi foreign key
    op.drop_constraint('fk_brands_store', 'brands', type_='foreignkey')
    
    # Rimuovi colonna
    op.drop_column('brands', 'id_store')
