"""create_ecommerce_order_states_table

Revision ID: f4157b4e4330
Revises: cf5576df2579
Create Date: 2025-12-16 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = 'f4157b4e4330'
down_revision: Union[str, None] = 'cf5576df2579'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()
    
    # Verifica se la tabella esiste già
    result = connection.execute(text("""
        SELECT COUNT(*) as count 
        FROM information_schema.TABLES 
        WHERE TABLE_SCHEMA = DATABASE() 
        AND TABLE_NAME = 'ecommerce_order_states'
    """))
    table_exists = result.fetchone()[0] > 0
    
    if not table_exists:
        # Crea tabella ecommerce_order_states
        op.create_table(
            'ecommerce_order_states',
            sa.Column('id_ecommerce_order_state', sa.Integer(), nullable=False),
            sa.Column('id_store', sa.Integer(), nullable=False),
            sa.Column('id_platform_state', sa.Integer(), nullable=False, comment='ID stato sulla piattaforma remota (PrestaShop, Shopify, ecc.)'),
            sa.Column('name', sa.String(200), nullable=False, comment='Nome dello stato sulla piattaforma remota'),
            sa.Column('platform_name', sa.String(50), nullable=False, comment='Nome della piattaforma (PrestaShop, Shopify, ecc.)'),
            sa.Column('date_add', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['id_store'], ['stores.id_store'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id_ecommerce_order_state'),
            sa.Index('ix_ecommerce_order_states_id_store', 'id_store'),
        )
        
        # Crea indice unico per (id_store, id_platform_state)
        op.create_index(
            'ix_ecommerce_order_states_store_platform_state',
            'ecommerce_order_states',
            ['id_store', 'id_platform_state'],
            unique=True
        )
    
    # Modifica orders.id_ecommerce_state per aggiungere foreign key
    result = connection.execute(text("""
        SELECT COUNT(*) as count
        FROM information_schema.KEY_COLUMN_USAGE
        WHERE TABLE_SCHEMA = DATABASE()
        AND TABLE_NAME = 'orders'
        AND CONSTRAINT_NAME = 'fk_orders_ecommerce_order_state'
    """))
    fk_exists = result.fetchone()[0] > 0
    
    if not fk_exists:
        # Prima rimuovi eventuali valori non validi (NULL è ok)
        # Poi aggiungi foreign key
        op.create_foreign_key(
            'fk_orders_ecommerce_order_state',
            'orders',
            'ecommerce_order_states',
            ['id_ecommerce_state'],
            ['id_ecommerce_order_state'],
            ondelete='SET NULL'
        )
    
    # Modifica platform_state_triggers.id_state_platform per aggiungere foreign key
    result = connection.execute(text("""
        SELECT COUNT(*) as count
        FROM information_schema.KEY_COLUMN_USAGE
        WHERE TABLE_SCHEMA = DATABASE()
        AND TABLE_NAME = 'platform_state_triggers'
        AND CONSTRAINT_NAME = 'fk_platform_state_triggers_ecommerce_order_state'
    """))
    fk_exists = result.fetchone()[0] > 0
    
    if not fk_exists:
        # Prima rendi nullable la colonna (se non lo è già)
        result = connection.execute(text("""
            SELECT IS_NULLABLE
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
            AND TABLE_NAME = 'platform_state_triggers'
            AND COLUMN_NAME = 'id_state_platform'
        """))
        nullable_result = result.fetchone()
        if nullable_result and nullable_result[0] == 'NO':
            op.alter_column('platform_state_triggers', 'id_state_platform',
                          existing_type=sa.Integer(),
                          nullable=True)
        
        # Aggiungi foreign key
        op.create_foreign_key(
            'fk_platform_state_triggers_ecommerce_order_state',
            'platform_state_triggers',
            'ecommerce_order_states',
            ['id_state_platform'],
            ['id_ecommerce_order_state'],
            ondelete='SET NULL'
        )


def downgrade() -> None:
    connection = op.get_bind()
    
    # Rimuovi foreign key da platform_state_triggers
    result = connection.execute(text("""
        SELECT CONSTRAINT_NAME
        FROM information_schema.KEY_COLUMN_USAGE
        WHERE TABLE_SCHEMA = DATABASE()
        AND TABLE_NAME = 'platform_state_triggers'
        AND CONSTRAINT_NAME = 'fk_platform_state_triggers_ecommerce_order_state'
    """))
    fk_result = result.fetchone()
    if fk_result:
        op.drop_constraint('fk_platform_state_triggers_ecommerce_order_state', 'platform_state_triggers', type_='foreignkey')
        # Ripristina NOT NULL se necessario
        op.alter_column('platform_state_triggers', 'id_state_platform',
                      existing_type=sa.Integer(),
                      nullable=False)
    
    # Rimuovi foreign key da orders
    result = connection.execute(text("""
        SELECT CONSTRAINT_NAME
        FROM information_schema.KEY_COLUMN_USAGE
        WHERE TABLE_SCHEMA = DATABASE()
        AND TABLE_NAME = 'orders'
        AND CONSTRAINT_NAME = 'fk_orders_ecommerce_order_state'
    """))
    fk_result = result.fetchone()
    if fk_result:
        op.drop_constraint('fk_orders_ecommerce_order_state', 'orders', type_='foreignkey')
    
    # Rimuovi tabella ecommerce_order_states
    result = connection.execute(text("""
        SELECT COUNT(*) as count
        FROM information_schema.TABLES
        WHERE TABLE_SCHEMA = DATABASE()
        AND TABLE_NAME = 'ecommerce_order_states'
    """))
    table_exists = result.fetchone()[0] > 0
    
    if table_exists:
        op.drop_index('ix_ecommerce_order_states_store_platform_state', table_name='ecommerce_order_states')
        op.drop_table('ecommerce_order_states')
