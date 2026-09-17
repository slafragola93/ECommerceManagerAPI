"""fiscal_document_detail product_qty to integer

Revision ID: b8c9d0e1f2a3
Revises: b7f8e9d0c1a2
Create Date: 2026-02-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b8c9d0e1f2a3'
down_revision: Union[str, None] = 'b7f8e9d0c1a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # PostgreSQL richiede USING per la conversione NUMERIC -> INTEGER
    conn = op.get_bind()
    if conn.dialect.name == 'postgresql':
        op.execute(
            "ALTER TABLE fiscal_document_details "
            "ALTER COLUMN product_qty TYPE INTEGER USING product_qty::integer"
        )
    else:
        op.alter_column(
            'fiscal_document_details',
            'product_qty',
            existing_type=sa.Numeric(10, 5),
            type_=sa.Integer(),
            existing_nullable=False,
            nullable=False,
        )


def downgrade() -> None:
    op.alter_column(
        'fiscal_document_details',
        'product_qty',
        existing_type=sa.Integer(),
        type_=sa.Numeric(10, 5),
        existing_nullable=False,
        nullable=False,
    )
