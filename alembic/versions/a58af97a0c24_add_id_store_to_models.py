"""add_id_store_to_models

Revision ID: a58af97a0c24
Revises: 749bce773e37
Create Date: 2025-12-12 15:11:07.004124

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = 'a58af97a0c24'
down_revision: Union[str, None] = '749bce773e37'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add id_store column to all tables (nullable initially)
    op.add_column('orders', sa.Column('id_store', sa.Integer(), nullable=True))
    op.add_column('products', sa.Column('id_store', sa.Integer(), nullable=True))
    op.add_column('customers', sa.Column('id_store', sa.Integer(), nullable=True))
    op.add_column('addresses', sa.Column('id_store', sa.Integer(), nullable=True))
    op.add_column('fiscal_documents', sa.Column('id_store', sa.Integer(), nullable=True))
    op.add_column('orders_document', sa.Column('id_store', sa.Integer(), nullable=True))
    
    # Create foreign keys
    op.create_foreign_key('fk_orders_store', 'orders', 'stores', ['id_store'], ['id_store'], ondelete='SET NULL')
    op.create_foreign_key('fk_products_store', 'products', 'stores', ['id_store'], ['id_store'], ondelete='SET NULL')
    op.create_foreign_key('fk_customers_store', 'customers', 'stores', ['id_store'], ['id_store'], ondelete='SET NULL')
    op.create_foreign_key('fk_addresses_store', 'addresses', 'stores', ['id_store'], ['id_store'], ondelete='SET NULL')
    op.create_foreign_key('fk_fiscal_documents_store', 'fiscal_documents', 'stores', ['id_store'], ['id_store'], ondelete='SET NULL')
    op.create_foreign_key('fk_orders_document_store', 'orders_document', 'stores', ['id_store'], ['id_store'], ondelete='SET NULL')
    
    # Create indexes
    op.create_index(op.f('ix_orders_id_store'), 'orders', ['id_store'], unique=False)
    op.create_index(op.f('ix_products_id_store'), 'products', ['id_store'], unique=False)
    op.create_index(op.f('ix_customers_id_store'), 'customers', ['id_store'], unique=False)
    op.create_index(op.f('ix_addresses_id_store'), 'addresses', ['id_store'], unique=False)
    op.create_index(op.f('ix_fiscal_documents_id_store'), 'fiscal_documents', ['id_store'], unique=False)
    op.create_index(op.f('ix_orders_document_id_store'), 'orders_document', ['id_store'], unique=False)
    
    # Migrate existing data: create default store and populate id_store
    conn = op.get_bind()
    
    # Get default platform (or use platform_id=1)
    platform_result = conn.execute(text("SELECT id_platform FROM platforms WHERE is_default = 1 LIMIT 1"))
    platform_row = platform_result.fetchone()
    if not platform_row:
        # Try to get platform with id=1
        platform_result = conn.execute(text("SELECT id_platform FROM platforms WHERE id_platform = 1 LIMIT 1"))
        platform_row = platform_result.fetchone()
        if not platform_row:
            # Create a default platform if none exists
            conn.execute(text("INSERT INTO platforms (id_platform, name, is_default) VALUES (1, 'PrestaShop', 1) ON DUPLICATE KEY UPDATE name='PrestaShop', is_default=1"))
            platform_id = 1
        else:
            platform_id = platform_row[0]
    else:
        platform_id = platform_row[0]
    
    # Get ecommerce configurations from app_configurations
    base_url_result = conn.execute(text("SELECT value FROM app_configurations WHERE category = 'ecommerce' AND name = 'base_url' LIMIT 1"))
    base_url_row = base_url_result.fetchone()
    base_url = base_url_row[0] if base_url_row else 'https://example.com'
    
    api_key_result = conn.execute(text("SELECT value FROM app_configurations WHERE category = 'ecommerce' AND name = 'api_key' LIMIT 1"))
    api_key_row = api_key_result.fetchone()
    api_key = api_key_row[0] if api_key_row else ''
    
    # Create default store
    conn.execute(text("""
        INSERT INTO stores (id_platform, name, base_url, api_key, is_active, is_default, date_add, updated_at)
        VALUES (:platform_id, 'Default Store', :base_url, :api_key, 1, 1, NOW(), NOW())
    """), {"platform_id": platform_id, "base_url": base_url, "api_key": api_key})
    
    # Get the created store ID
    store_result = conn.execute(text("SELECT id_store FROM stores WHERE is_default = 1 LIMIT 1"))
    store_row = store_result.fetchone()
    if store_row:
        default_store_id = store_row[0]
        
        # Populate id_store in existing records based on id_platform
        # For orders: use id_platform to determine store (for now, all go to default store)
        conn.execute(text("UPDATE orders SET id_store = :store_id WHERE id_store IS NULL"), {"store_id": default_store_id})
        
        # For products: use id_platform to determine store
        conn.execute(text("UPDATE products SET id_store = :store_id WHERE id_store IS NULL"), {"store_id": default_store_id})
        
        # For customers: assign to default store
        conn.execute(text("UPDATE customers SET id_store = :store_id WHERE id_store IS NULL"), {"store_id": default_store_id})
        
        # For addresses: use id_platform to determine store
        conn.execute(text("UPDATE addresses SET id_store = :store_id WHERE id_store IS NULL"), {"store_id": default_store_id})
        
        # For fiscal_documents: get from order
        conn.execute(text("""
            UPDATE fiscal_documents fd
            INNER JOIN orders o ON fd.id_order = o.id_order
            SET fd.id_store = o.id_store
            WHERE fd.id_store IS NULL
        """))
        
        # For orders_document: get from order
        conn.execute(text("""
            UPDATE orders_document od
            INNER JOIN orders o ON od.id_order = o.id_order
            SET od.id_store = o.id_store
            WHERE od.id_store IS NULL
        """))
    
    # Note: We keep id_store nullable for now to allow flexibility during transition
    # After validation, we can make it NOT NULL in a future migration


def downgrade() -> None:
    # Drop indexes
    op.drop_index(op.f('ix_orders_document_id_store'), table_name='orders_document')
    op.drop_index(op.f('ix_fiscal_documents_id_store'), table_name='fiscal_documents')
    op.drop_index(op.f('ix_addresses_id_store'), table_name='addresses')
    op.drop_index(op.f('ix_customers_id_store'), table_name='customers')
    op.drop_index(op.f('ix_products_id_store'), table_name='products')
    op.drop_index(op.f('ix_orders_id_store'), table_name='orders')
    
    # Drop foreign keys
    op.drop_constraint('fk_orders_document_store', 'orders_document', type_='foreignkey')
    op.drop_constraint('fk_fiscal_documents_store', 'fiscal_documents', type_='foreignkey')
    op.drop_constraint('fk_addresses_store', 'addresses', type_='foreignkey')
    op.drop_constraint('fk_customers_store', 'customers', type_='foreignkey')
    op.drop_constraint('fk_products_store', 'products', type_='foreignkey')
    op.drop_constraint('fk_orders_store', 'orders', type_='foreignkey')
    
    # Drop columns
    op.drop_column('orders_document', 'id_store')
    op.drop_column('fiscal_documents', 'id_store')
    op.drop_column('addresses', 'id_store')
    op.drop_column('customers', 'id_store')
    op.drop_column('products', 'id_store')
    op.drop_column('orders', 'id_store')
