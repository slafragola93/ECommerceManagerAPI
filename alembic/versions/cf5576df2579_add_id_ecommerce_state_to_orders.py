"""add_id_ecommerce_state_to_orders

Revision ID: cf5576df2579
Revises: fd1c3139242c
Create Date: 2025-12-16 10:46:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = 'cf5576df2579'
down_revision: Union[str, None] = 'fd1c3139242c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()
    
    # Verifica se la colonna esiste già
    result = connection.execute(text("""
        SELECT COUNT(*) as count 
        FROM information_schema.COLUMNS 
        WHERE TABLE_SCHEMA = DATABASE() 
        AND TABLE_NAME = 'orders' 
        AND COLUMN_NAME = 'id_ecommerce_state'
    """))
    column_exists = result.fetchone()[0] > 0
    
    if not column_exists:
        # Aggiungi colonna id_ecommerce_state
        op.add_column('orders', sa.Column(
            'id_ecommerce_state', 
            sa.Integer(), 
            nullable=True,
            comment='ID stato corrente sull\'e-commerce remoto (PrestaShop, Shopify, ecc.)'
        ))
        
        # Crea indice
        op.create_index(
            op.f('ix_orders_id_ecommerce_state'),
            'orders',
            ['id_ecommerce_state'],
            unique=False
        )


def downgrade() -> None:
    connection = op.get_bind()
    
    # Verifica se la colonna esiste
    result = connection.execute(text("""
        SELECT COUNT(*) as count
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
        AND TABLE_NAME = 'orders'
        AND COLUMN_NAME = 'id_ecommerce_state'
    """))
    column_exists = result.fetchone()[0] > 0
    
    if column_exists:
        # Rimuovi indice
        result = connection.execute(text("""
            SELECT INDEX_NAME
            FROM information_schema.STATISTICS
            WHERE TABLE_SCHEMA = DATABASE()
            AND TABLE_NAME = 'orders'
            AND INDEX_NAME = 'ix_orders_id_ecommerce_state'
        """))
        index_result = result.fetchone()
        if index_result:
            op.drop_index(op.f('ix_orders_id_ecommerce_state'), table_name='orders')
        
        # Rimuovi colonna
        op.drop_column('orders', 'id_ecommerce_state')
