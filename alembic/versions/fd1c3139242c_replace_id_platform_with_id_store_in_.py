"""replace_id_platform_with_id_store_in_triggers

Revision ID: fd1c3139242c
Revises: ed8f92f38a64
Create Date: 2025-12-16 10:45:42.077846

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = 'fd1c3139242c'
down_revision: Union[str, None] = 'ed8f92f38a64'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()
    
    # Verifica se la colonna id_store esiste già
    result = connection.execute(text("""
        SELECT COUNT(*) as count 
        FROM information_schema.COLUMNS 
        WHERE TABLE_SCHEMA = DATABASE() 
        AND TABLE_NAME = 'platform_state_triggers' 
        AND COLUMN_NAME = 'id_store'
    """))
    column_exists = result.fetchone()[0] > 0
    
    if not column_exists:
        # 1. Aggiungi colonna id_store (nullable temporaneamente)
        op.add_column('platform_state_triggers', sa.Column('id_store', sa.Integer(), nullable=True))
        
        # 2. Migra dati: per ogni trigger, recupera id_store dalla piattaforma associata
        # Usa JOIN tra platform_state_triggers e stores tramite id_platform
        connection.execute(text("""
            UPDATE platform_state_triggers pst
            INNER JOIN stores s ON pst.id_platform = s.id_platform
            SET pst.id_store = s.id_store
            WHERE pst.id_store IS NULL
        """))
        
        # 3. Se ci sono trigger senza store corrispondente, usa il primo store disponibile come default
        result = connection.execute(text("SELECT id_store FROM stores ORDER BY id_store LIMIT 1"))
        first_store = result.fetchone()
        default_store_id = first_store[0] if first_store else 1
        
        connection.execute(text(f"""
            UPDATE platform_state_triggers
            SET id_store = {default_store_id}
            WHERE id_store IS NULL
        """))
        
        # 4. Rendere id_store NOT NULL
        op.alter_column('platform_state_triggers', 'id_store', nullable=False)
    
    # 5. Rimuovi foreign key esistente per id_platform
    result = connection.execute(text("""
        SELECT CONSTRAINT_NAME
        FROM information_schema.KEY_COLUMN_USAGE
        WHERE TABLE_SCHEMA = DATABASE()
        AND TABLE_NAME = 'platform_state_triggers'
        AND COLUMN_NAME = 'id_platform'
        AND REFERENCED_TABLE_NAME = 'platforms'
    """))
    fk_result = result.fetchone()
    if fk_result:
        fk_name = fk_result[0]
        op.drop_constraint(fk_name, 'platform_state_triggers', type_='foreignkey')
    
    # 6. Crea foreign key per id_store
    result = connection.execute(text("""
        SELECT COUNT(*) as count
        FROM information_schema.KEY_COLUMN_USAGE
        WHERE TABLE_SCHEMA = DATABASE()
        AND TABLE_NAME = 'platform_state_triggers'
        AND CONSTRAINT_NAME = 'fk_platform_state_triggers_store'
    """))
    fk_exists = result.fetchone()[0] > 0
    
    if not fk_exists:
        op.create_foreign_key(
            'fk_platform_state_triggers_store',
            'platform_state_triggers',
            'stores',
            ['id_store'],
            ['id_store'],
            ondelete='CASCADE'
        )
    
    # 7. Aggiorna indici
    # Rimuovi indice vecchio idx_event_platform se esiste
    result = connection.execute(text("""
        SELECT INDEX_NAME
        FROM information_schema.STATISTICS
        WHERE TABLE_SCHEMA = DATABASE()
        AND TABLE_NAME = 'platform_state_triggers'
        AND INDEX_NAME = 'idx_event_platform'
    """))
    index_result = result.fetchone()
    if index_result:
        op.drop_index('idx_event_platform', table_name='platform_state_triggers')
    
    # Crea nuovo indice idx_event_store
    result = connection.execute(text("""
        SELECT COUNT(*) as count
        FROM information_schema.STATISTICS
        WHERE TABLE_SCHEMA = DATABASE()
        AND TABLE_NAME = 'platform_state_triggers'
        AND INDEX_NAME = 'idx_event_store'
    """))
    index_exists = result.fetchone()[0] > 0
    
    if not index_exists:
        op.create_index('idx_event_store', 'platform_state_triggers', ['event_type', 'id_store'])
    
    # Crea indice per id_store se non esiste
    result = connection.execute(text("""
        SELECT COUNT(*) as count
        FROM information_schema.STATISTICS
        WHERE TABLE_SCHEMA = DATABASE()
        AND TABLE_NAME = 'platform_state_triggers'
        AND INDEX_NAME = 'ix_platform_state_triggers_id_store'
    """))
    index_exists = result.fetchone()[0] > 0
    
    if not index_exists:
        op.create_index(
            op.f('ix_platform_state_triggers_id_store'),
            'platform_state_triggers',
            ['id_store'],
            unique=False
        )
    
    # 8. Rimuovi colonna id_platform
    result = connection.execute(text("""
        SELECT COUNT(*) as count
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
        AND TABLE_NAME = 'platform_state_triggers'
        AND COLUMN_NAME = 'id_platform'
    """))
    column_exists = result.fetchone()[0] > 0
    
    if column_exists:
        op.drop_column('platform_state_triggers', 'id_platform')


def downgrade() -> None:
    connection = op.get_bind()
    
    # 1. Aggiungi colonna id_platform (nullable temporaneamente)
    result = connection.execute(text("""
        SELECT COUNT(*) as count
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
        AND TABLE_NAME = 'platform_state_triggers'
        AND COLUMN_NAME = 'id_platform'
    """))
    column_exists = result.fetchone()[0] > 0
    
    if not column_exists:
        op.add_column('platform_state_triggers', sa.Column('id_platform', sa.Integer(), nullable=True))
        
        # Migra dati: recupera id_platform dallo store
        connection.execute(text("""
            UPDATE platform_state_triggers pst
            INNER JOIN stores s ON pst.id_store = s.id_store
            SET pst.id_platform = s.id_platform
            WHERE pst.id_platform IS NULL
        """))
        
        # Se ci sono trigger senza piattaforma, usa default
        result = connection.execute(text("SELECT id_platform FROM platforms ORDER BY id_platform LIMIT 1"))
        first_platform = result.fetchone()
        default_platform_id = first_platform[0] if first_platform else 1
        
        connection.execute(text(f"""
            UPDATE platform_state_triggers
            SET id_platform = {default_platform_id}
            WHERE id_platform IS NULL
        """))
        
        op.alter_column('platform_state_triggers', 'id_platform', nullable=False)
    
    # 2. Rimuovi foreign key per id_store
    result = connection.execute(text("""
        SELECT CONSTRAINT_NAME
        FROM information_schema.KEY_COLUMN_USAGE
        WHERE TABLE_SCHEMA = DATABASE()
        AND TABLE_NAME = 'platform_state_triggers'
        AND CONSTRAINT_NAME = 'fk_platform_state_triggers_store'
    """))
    fk_result = result.fetchone()
    if fk_result:
        op.drop_constraint('fk_platform_state_triggers_store', 'platform_state_triggers', type_='foreignkey')
    
    # 3. Crea foreign key per id_platform
    result = connection.execute(text("""
        SELECT COUNT(*) as count
        FROM information_schema.KEY_COLUMN_USAGE
        WHERE TABLE_SCHEMA = DATABASE()
        AND TABLE_NAME = 'platform_state_triggers'
        AND CONSTRAINT_NAME = 'fk_platform_state_triggers_platform'
    """))
    fk_exists = result.fetchone()[0] > 0
    
    if not fk_exists:
        op.create_foreign_key(
            'fk_platform_state_triggers_platform',
            'platform_state_triggers',
            'platforms',
            ['id_platform'],
            ['id_platform'],
            ondelete='CASCADE'
        )
    
    # 4. Aggiorna indici
    # Rimuovi idx_event_store
    result = connection.execute(text("""
        SELECT INDEX_NAME
        FROM information_schema.STATISTICS
        WHERE TABLE_SCHEMA = DATABASE()
        AND TABLE_NAME = 'platform_state_triggers'
        AND INDEX_NAME = 'idx_event_store'
    """))
    index_result = result.fetchone()
    if index_result:
        op.drop_index('idx_event_store', table_name='platform_state_triggers')
    
    # Crea idx_event_platform
    result = connection.execute(text("""
        SELECT COUNT(*) as count
        FROM information_schema.STATISTICS
        WHERE TABLE_SCHEMA = DATABASE()
        AND TABLE_NAME = 'platform_state_triggers'
        AND INDEX_NAME = 'idx_event_platform'
    """))
    index_exists = result.fetchone()[0] > 0
    
    if not index_exists:
        op.create_index('idx_event_platform', 'platform_state_triggers', ['event_type', 'id_platform'])
    
    # Rimuovi indice id_store
    result = connection.execute(text("""
        SELECT INDEX_NAME
        FROM information_schema.STATISTICS
        WHERE TABLE_SCHEMA = DATABASE()
        AND TABLE_NAME = 'platform_state_triggers'
        AND INDEX_NAME = 'ix_platform_state_triggers_id_store'
    """))
    index_result = result.fetchone()
    if index_result:
        op.drop_index(op.f('ix_platform_state_triggers_id_store'), table_name='platform_state_triggers')
    
    # 5. Rimuovi colonna id_store
    result = connection.execute(text("""
        SELECT COUNT(*) as count
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
        AND TABLE_NAME = 'platform_state_triggers'
        AND COLUMN_NAME = 'id_store'
    """))
    column_exists = result.fetchone()[0] > 0
    
    if column_exists:
        op.drop_column('platform_state_triggers', 'id_store')
