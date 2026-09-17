"""add_products_total_price_fields_to_orders_and_order_documents

Revision ID: 77a97ae89e14
Revises: 9e03c7965b78
Create Date: 2025-12-02 09:42:41.117977

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql
from sqlalchemy.sql import text

# revision identifiers, used by Alembic.
revision: str = '77a97ae89e14'
down_revision: Union[str, None] = '9e03c7965b78'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Aggiungi colonne products_total_price_net e products_total_price_with_tax a orders
    op.add_column('orders', sa.Column('products_total_price_net', sa.Numeric(precision=10, scale=5), nullable=False, server_default='0.0'))
    op.add_column('orders', sa.Column('products_total_price_with_tax', sa.Numeric(precision=10, scale=5), nullable=False, server_default='0.0'))
    
    # Popola i valori esistenti per orders
    op.execute(text("""
        UPDATE orders o
        SET o.products_total_price_net = COALESCE((
            SELECT SUM(od.total_price_net)
            FROM order_details od
            WHERE od.id_order = o.id_order
            AND (od.id_order_document IS NULL OR od.id_order_document = 0)
        ), 0.0),
        o.products_total_price_with_tax = COALESCE((
            SELECT SUM(od.total_price_with_tax)
            FROM order_details od
            WHERE od.id_order = o.id_order
            AND (od.id_order_document IS NULL OR od.id_order_document = 0)
        ), 0.0)
    """))
    
    # Aggiungi colonne products_total_price_net e products_total_price_with_tax a orders_document
    op.add_column('orders_document', sa.Column('products_total_price_net', sa.Numeric(precision=10, scale=5), nullable=True, server_default='0.0'))
    op.add_column('orders_document', sa.Column('products_total_price_with_tax', sa.Numeric(precision=10, scale=5), nullable=True, server_default='0.0'))
    
    # Popola i valori esistenti per orders_document
    op.execute(text("""
        UPDATE orders_document od
        SET od.products_total_price_net = COALESCE((
            SELECT SUM(odetail.total_price_net)
            FROM order_details odetail
            WHERE odetail.id_order_document = od.id_order_document
            AND (odetail.id_order IS NULL OR odetail.id_order = 0)
        ), 0.0),
        od.products_total_price_with_tax = COALESCE((
            SELECT SUM(odetail.total_price_with_tax)
            FROM order_details odetail
            WHERE odetail.id_order_document = od.id_order_document
            AND (odetail.id_order IS NULL OR odetail.id_order = 0)
        ), 0.0)
    """))


def downgrade() -> None:
    # Rimuovi colonne products_total_price_net e products_total_price_with_tax da orders_document
    op.drop_column('orders_document', 'products_total_price_with_tax')
    op.drop_column('orders_document', 'products_total_price_net')
    
    # Rimuovi colonne products_total_price_net e products_total_price_with_tax da orders
    op.drop_column('orders', 'products_total_price_with_tax')
    op.drop_column('orders', 'products_total_price_net')
