"""add_id_store_to_categories

Revision ID: 907004240072
Revises: f0caf316364f
Create Date: 2025-12-15 12:01:53.819570

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '907004240072'
down_revision: Union[str, None] = 'f0caf316364f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Aggiungi colonna id_store alla tabella categories
    op.add_column('categories', sa.Column('id_store', sa.Integer(), nullable=False, server_default='1'))
    
    # Crea foreign key
    op.create_foreign_key(
        'fk_categories_store',
        'categories',
        'stores',
        ['id_store'],
        ['id_store'],
        ondelete='RESTRICT'
    )
    
    # Crea indice
    op.create_index(
        op.f('ix_categories_id_store'),
        'categories',
        ['id_store'],
        unique=False
    )


def downgrade() -> None:
    # Rimuovi indice
    op.drop_index(op.f('ix_categories_id_store'), table_name='categories')
    
    # Rimuovi foreign key
    op.drop_constraint('fk_categories_store', 'categories', type_='foreignkey')
    
    # Rimuovi colonna
    op.drop_column('categories', 'id_store')
