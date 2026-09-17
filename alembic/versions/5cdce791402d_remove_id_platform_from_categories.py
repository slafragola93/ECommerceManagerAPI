"""remove_id_platform_from_categories

Revision ID: 5cdce791402d
Revises: 6a5e4a6b1f3b
Create Date: 2026-01-27 11:40:19.590293

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5cdce791402d'
down_revision: Union[str, None] = '6a5e4a6b1f3b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    if 'categories' not in inspector.get_table_names():
        return
    
    # Verifica se la colonna esiste
    columns = [col['name'] for col in inspector.get_columns('categories')]
    if 'id_platform' not in columns:
        print("id_platform column does not exist in categories, skipping")
        return
    
    # 1. Rimuovi foreign key se esiste
    fks = inspector.get_foreign_keys('categories')
    fk_to_remove = None
    for fk in fks:
        if fk['constrained_columns'] == ['id_platform'] and fk.get('name') == 'fk_categories_platform':
            fk_to_remove = fk['name']
            break
        # Cerca anche per pattern alternativo
        if fk['constrained_columns'] == ['id_platform'] and 'platform' in fk.get('name', '').lower():
            fk_to_remove = fk['name']
            break
    
    if fk_to_remove:
        op.drop_constraint(fk_to_remove, 'categories', type_='foreignkey')
        print(f"Removed foreign key {fk_to_remove} from categories")
    
    # 2. Rimuovi indice se esiste
    indexes = {idx['name'] for idx in inspector.get_indexes('categories')}
    if 'ix_categories_id_platform' in indexes:
        op.drop_index(op.f('ix_categories_id_platform'), table_name='categories')
        print("Removed index ix_categories_id_platform from categories")
    
    # 3. Rimuovi colonna
    op.drop_column('categories', 'id_platform')
    print("Removed id_platform column from categories")


def downgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    if 'categories' not in inspector.get_table_names():
        return
    
    columns = [col['name'] for col in inspector.get_columns('categories')]
    if 'id_platform' not in columns:
        # Aggiungi colonna
        op.add_column('categories', sa.Column('id_platform', sa.Integer(), nullable=True))
        
        # Aggiungi indice
        op.create_index(
            op.f('ix_categories_id_platform'),
            'categories',
            ['id_platform'],
            unique=False
        )
        
        # Aggiungi foreign key
        op.create_foreign_key(
            'fk_categories_platform',
            'categories',
            'platforms',
            ['id_platform'],
            ['id_platform']
        )
        print("Restored id_platform column, index and foreign key to categories")