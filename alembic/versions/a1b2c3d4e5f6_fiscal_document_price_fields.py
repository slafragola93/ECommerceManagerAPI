"""fiscal_document_price_fields

Revision ID: b7f8e9d0c1a2
Revises: 81fd95d3c75d, ad34c0277fad
Create Date: 2026-01-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b7f8e9d0c1a2'
down_revision: Union[str, None] = ('81fd95d3c75d', 'ad34c0277fad')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- fiscal_documents ---
    # Add new price columns
    op.add_column('fiscal_documents', sa.Column('total_price_with_tax', sa.Numeric(10, 5), nullable=True))
    op.add_column('fiscal_documents', sa.Column('total_price_net', sa.Numeric(10, 5), nullable=True))
    op.add_column('fiscal_documents', sa.Column('products_total_price_net', sa.Numeric(10, 5), nullable=True))
    op.add_column('fiscal_documents', sa.Column('products_total_price_with_tax', sa.Numeric(10, 5), nullable=True))
    # Copy data from total_amount
    op.execute("UPDATE fiscal_documents SET total_price_with_tax = total_amount WHERE total_amount IS NOT NULL")
    op.execute("UPDATE fiscal_documents SET products_total_price_with_tax = total_amount WHERE total_amount IS NOT NULL")
    op.execute("UPDATE fiscal_documents SET products_total_price_net = total_amount WHERE total_amount IS NOT NULL")
    op.execute("UPDATE fiscal_documents SET total_price_net = total_amount WHERE total_amount IS NOT NULL")
    # Drop old column
    op.drop_column('fiscal_documents', 'total_amount')

    # --- fiscal_document_details ---
    # Rename quantity -> product_qty
    op.alter_column(
        'fiscal_document_details',
        'quantity',
        new_column_name='product_qty',
        existing_type=sa.Numeric(10, 5),
        existing_nullable=False
    )
    # Drop total_amount
    op.drop_column('fiscal_document_details', 'total_amount')


def downgrade() -> None:
    # --- fiscal_document_details ---
    op.add_column('fiscal_document_details', sa.Column('total_amount', sa.Numeric(10, 5), nullable=True))
    op.execute("UPDATE fiscal_document_details SET total_amount = total_price_with_tax")
    op.alter_column(
        'fiscal_document_details',
        'total_amount',
        existing_type=sa.Numeric(10, 5),
        nullable=False
    )
    op.alter_column(
        'fiscal_document_details',
        'product_qty',
        new_column_name='quantity',
        existing_type=sa.Numeric(10, 5),
        existing_nullable=False
    )

    # --- fiscal_documents ---
    op.add_column('fiscal_documents', sa.Column('total_amount', sa.Numeric(10, 5), nullable=True))
    op.execute("UPDATE fiscal_documents SET total_amount = total_price_with_tax")
    op.drop_column('fiscal_documents', 'products_total_price_with_tax')
    op.drop_column('fiscal_documents', 'products_total_price_net')
    op.drop_column('fiscal_documents', 'total_price_net')
    op.drop_column('fiscal_documents', 'total_price_with_tax')