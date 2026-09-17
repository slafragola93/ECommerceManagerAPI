"""remove_id_platform_from_models

Revision ID: 2d6cca22110a
Revises: a58af97a0c24
Create Date: 2025-12-20 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '2d6cca22110a'
down_revision: Union[str, None] = 'a58af97a0c24'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Remove id_platform column from products and addresses only
    # Note: Orders keeps id_platform for backward compatibility
    # Note: Category and Brand keep id_platform as they are shared between stores
    
    # Check if index exists before dropping (MySQL compatible)
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    
    # Drop index for products if exists
    try:
        indexes = [idx['name'] for idx in inspector.get_indexes('products')]
        if 'ix_products_id_platform' in indexes:
            op.drop_index('ix_products_id_platform', table_name='products')
    except Exception:
        pass
    
    # Drop index for addresses if exists
    try:
        indexes = [idx['name'] for idx in inspector.get_indexes('addresses')]
        if 'ix_addresses_id_platform' in indexes:
            op.drop_index('ix_addresses_id_platform', table_name='addresses')
    except Exception:
        pass
    
    # Drop foreign key constraints if they exist (only for products and addresses)
    # MySQL requires checking constraint names first
    try:
        fk_constraints = [fk['name'] for fk in inspector.get_foreign_keys('products')]
        if 'fk_products_platform' in fk_constraints:
            op.drop_constraint('fk_products_platform', 'products', type_='foreignkey')
    except Exception:
        pass
    
    try:
        fk_constraints = [fk['name'] for fk in inspector.get_foreign_keys('addresses')]
        if 'fk_addresses_platform' in fk_constraints:
            op.drop_constraint('fk_addresses_platform', 'addresses', type_='foreignkey')
    except Exception:
        pass
    
    # Drop columns (only products and addresses, NOT orders)
    # Check if column exists first
    try:
        products_columns = [col['name'] for col in inspector.get_columns('products')]
        if 'id_platform' in products_columns:
            op.drop_column('products', 'id_platform')
    except Exception:
        pass
    
    try:
        addresses_columns = [col['name'] for col in inspector.get_columns('addresses')]
        if 'id_platform' in addresses_columns:
            op.drop_column('addresses', 'id_platform')
    except Exception:
        pass


def downgrade() -> None:
    # Add id_platform columns back (nullable) - only for products and addresses
    # Note: orders already has id_platform, so we don't add it again
    op.add_column('products', sa.Column('id_platform', sa.Integer(), nullable=True))
    op.add_column('addresses', sa.Column('id_platform', sa.Integer(), nullable=True))
    
    # Create foreign keys (only for products and addresses)
    op.create_foreign_key('fk_products_platform', 'products', 'platforms', ['id_platform'], ['id_platform'], ondelete='SET NULL')
    op.create_foreign_key('fk_addresses_platform', 'addresses', 'platforms', ['id_platform'], ['id_platform'], ondelete='SET NULL')
    
    # Create indexes (only for products and addresses)
    op.create_index(op.f('ix_products_id_platform'), 'products', ['id_platform'], unique=False)
    op.create_index(op.f('ix_addresses_id_platform'), 'addresses', ['id_platform'], unique=False)
