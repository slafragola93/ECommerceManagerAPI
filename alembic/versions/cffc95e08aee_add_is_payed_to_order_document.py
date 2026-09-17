"""add_is_payed_to_order_document

Revision ID: cffc95e08aee
Revises: a1b2c3d4e5f6
Create Date: 2025-11-17 11:12:37.829612

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cffc95e08aee'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Aggiunge colonna is_payed alla tabella orders_document"""
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    existing_columns = [col['name'] for col in inspector.get_columns('orders_document')]
    
    if 'is_payed' not in existing_columns:
        op.add_column(
            'orders_document',
            sa.Column('is_payed', sa.Boolean(), nullable=True, default=None)
        )
        print("Successfully added is_payed column to orders_document table")


def downgrade() -> None:
    """Rimuove colonna is_payed dalla tabella orders_document"""
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    existing_columns = [col['name'] for col in inspector.get_columns('orders_document')]
    
    if 'is_payed' in existing_columns:
        op.drop_column('orders_document', 'is_payed')
        print("Successfully dropped is_payed column from orders_document table")
