"""remove_payment_type_use_customs_charges

Revision ID: 6b6f2f043e54
Revises: 23731ef84889
Create Date: 2025-11-20 16:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = '6b6f2f043e54'
down_revision: Union[str, None] = '23731ef84889'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### FedEx Configuration updates only ###
    # Check existing columns to avoid errors
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_columns = [col['name'] for col in inspector.get_columns('fedex_configurations')]
    
    # Remove payment_type column if it exists
    if 'payment_type' in existing_columns:
        op.drop_column('fedex_configurations', 'payment_type')
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### FedEx Configuration rollback only ###
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_columns = [col['name'] for col in inspector.get_columns('fedex_configurations')]
    
    # Re-add payment_type column if it doesn't exist
    if 'payment_type' not in existing_columns:
        op.add_column('fedex_configurations', sa.Column('payment_type', sa.String(length=50), nullable=True))
    # ### end Alembic commands ###
