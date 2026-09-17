"""add_id_store_to_app_configurations

Revision ID: 930bc8cbac0f
Revises: 2d6cca22110a
Create Date: 2025-12-12 16:10:09.247028

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '930bc8cbac0f'
down_revision: Union[str, None] = '2d6cca22110a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Check if column exists before adding (MySQL compatible)
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    
    # Check if id_store column already exists
    columns = [col['name'] for col in inspector.get_columns('app_configurations')]
    
    if 'id_store' not in columns:
        # Add id_store column to app_configurations (nullable initially)
        op.add_column('app_configurations', sa.Column('id_store', sa.Integer(), nullable=True))
    
    # Check if foreign key exists before creating
    fk_constraints = [fk['name'] for fk in inspector.get_foreign_keys('app_configurations')]
    if 'fk_app_configurations_store' not in fk_constraints:
        # Create foreign key
        op.create_foreign_key(
            'fk_app_configurations_store',
            'app_configurations',
            'stores',
            ['id_store'],
            ['id_store'],
            ondelete='SET NULL'
        )
    
    # Check if index exists before creating
    indexes = [idx['name'] for idx in inspector.get_indexes('app_configurations')]
    if 'ix_app_configurations_id_store' not in indexes:
        # Create index
        op.create_index(
            op.f('ix_app_configurations_id_store'),
            'app_configurations',
            ['id_store'],
            unique=False
        )
    
    # Migrate existing data: assign to default store (id_store = 1)
    # Get default store ID
    store_result = conn.execute(sa.text("SELECT id_store FROM stores WHERE is_default = 1 LIMIT 1"))
    store_row = store_result.fetchone()
    
    if store_row:
        default_store_id = store_row[0]
        # Update existing app_configurations to point to default store
        conn.execute(
            sa.text("UPDATE app_configurations SET id_store = :store_id WHERE id_store IS NULL"),
            {"store_id": default_store_id}
        )
        conn.commit()
    
    # Note: id_store remains nullable to allow global configurations if needed


def downgrade() -> None:
    # Drop index
    op.drop_index(op.f('ix_app_configurations_id_store'), table_name='app_configurations')
    
    # Drop foreign key
    op.drop_constraint('fk_app_configurations_store', 'app_configurations', type_='foreignkey')
    
    # Drop column
    op.drop_column('app_configurations', 'id_store')
