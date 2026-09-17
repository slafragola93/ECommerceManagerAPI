"""create_stores_table

Revision ID: 749bce773e37
Revises: f49ad02321c1
Create Date: 2025-12-20 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = '749bce773e37'
down_revision: Union[str, None] = 'f49ad02321c1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create stores table
    op.create_table('stores',
        sa.Column('id_store', sa.Integer(), nullable=False),
        sa.Column('id_platform', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('base_url', sa.String(500), nullable=False),
        sa.Column('api_key', sa.String(500), nullable=False),
        sa.Column('vat_number', sa.String(50), nullable=True),
        sa.Column('country_code', sa.String(5), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('date_add', sa.DateTime(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['id_platform'], ['platforms.id_platform'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id_store')
    )
    
    # Create indexes
    op.create_index(op.f('ix_stores_id_store'), 'stores', ['id_store'], unique=False)
    op.create_index(op.f('ix_stores_id_platform'), 'stores', ['id_platform'], unique=False)
    op.create_index(op.f('ix_stores_vat_number'), 'stores', ['vat_number'], unique=False)
    op.create_index(op.f('ix_stores_country_code'), 'stores', ['country_code'], unique=False)


def downgrade() -> None:
    # Drop indexes
    op.drop_index(op.f('ix_stores_country_code'), table_name='stores')
    op.drop_index(op.f('ix_stores_vat_number'), table_name='stores')
    op.drop_index(op.f('ix_stores_id_platform'), table_name='stores')
    op.drop_index(op.f('ix_stores_id_store'), table_name='stores')
    
    # Drop table
    op.drop_table('stores')
