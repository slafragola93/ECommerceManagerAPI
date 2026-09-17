"""remove_fedex_oauth_fields_add_contact_email

Revision ID: 23731ef84889
Revises: ed4917ba275c
Create Date: 2025-11-20 16:39:14.845015

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = '23731ef84889'
down_revision: Union[str, None] = 'ed4917ba275c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### FedEx Configuration updates only ###
    # Check existing columns to avoid errors
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_columns = [col['name'] for col in inspector.get_columns('fedex_configurations')]
    
    # Add contact_email if it doesn't exist
    if 'contact_email' not in existing_columns:
        op.add_column('fedex_configurations', sa.Column('contact_email', sa.String(length=255), nullable=True))
    
    # Remove columns if they exist
    columns_to_remove = [
        'grant_type',
        'child_key',
        'child_secret',
        'shipper_address',
        'shipper_contact',
        'label_stock_type',
        'label_format_type',
        'label_print_type'
    ]
    
    for col_name in columns_to_remove:
        if col_name in existing_columns:
            op.drop_column('fedex_configurations', col_name)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### FedEx Configuration rollback only ###
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_columns = [col['name'] for col in inspector.get_columns('fedex_configurations')]
    
    # Re-add removed columns
    if 'grant_type' not in existing_columns:
        op.add_column('fedex_configurations', sa.Column('grant_type', sa.String(length=50), nullable=True, server_default='client_credentials'))
    if 'child_key' not in existing_columns:
        op.add_column('fedex_configurations', sa.Column('child_key', sa.String(length=255), nullable=True))
    if 'child_secret' not in existing_columns:
        op.add_column('fedex_configurations', sa.Column('child_secret', sa.String(length=255), nullable=True))
    if 'shipper_address' not in existing_columns:
        op.add_column('fedex_configurations', sa.Column('shipper_address', sa.Text(), nullable=True))
    if 'shipper_contact' not in existing_columns:
        op.add_column('fedex_configurations', sa.Column('shipper_contact', sa.Text(), nullable=True))
    if 'label_stock_type' not in existing_columns:
        op.add_column('fedex_configurations', sa.Column('label_stock_type', sa.String(length=50), nullable=True))
    if 'label_format_type' not in existing_columns:
        op.add_column('fedex_configurations', sa.Column('label_format_type', sa.String(length=50), nullable=True))
    if 'label_print_type' not in existing_columns:
        op.add_column('fedex_configurations', sa.Column('label_print_type', sa.String(length=50), nullable=True))
    
    # Remove contact_email if it exists
    if 'contact_email' in existing_columns:
        op.drop_column('fedex_configurations', 'contact_email')
    # ### end Alembic commands ###
