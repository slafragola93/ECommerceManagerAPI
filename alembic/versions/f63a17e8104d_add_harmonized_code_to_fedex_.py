"""add_harmonized_code_to_fedex_configurations

Revision ID: f63a17e8104d
Revises: f4157b4e4330
Create Date: 2026-01-12 11:11:41.313134

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f63a17e8104d'
down_revision: Union[str, None] = 'cf5576df2579'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add harmonized_code column to fedex_configurations table
    op.add_column('fedex_configurations', sa.Column('harmonized_code', sa.String(length=20), nullable=True))


def downgrade() -> None:
    # Remove harmonized_code column from fedex_configurations table
    op.drop_column('fedex_configurations', 'harmonized_code')
