"""update_fedex_configuration_add_oauth_and_new_fields

Revision ID: ed4917ba275c
Revises: 4000ddbfb949
Create Date: 2025-11-20 16:24:30.370737

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = 'ed4917ba275c'
down_revision: Union[str, None] = '4000ddbfb949'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### FedEx Configuration updates only ###
    # Check existing columns to avoid duplicates
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_columns = [col['name'] for col in inspector.get_columns('fedex_configurations')]
    
    # Add OAuth 2.0 fields
    if 'grant_type' not in existing_columns:
        op.add_column('fedex_configurations', sa.Column('grant_type', sa.String(length=50), nullable=True, server_default='client_credentials'))
    if 'child_key' not in existing_columns:
        op.add_column('fedex_configurations', sa.Column('child_key', sa.String(length=255), nullable=True))
    if 'child_secret' not in existing_columns:
        op.add_column('fedex_configurations', sa.Column('child_secret', sa.String(length=255), nullable=True))
    
    # Add shipper complete data fields
    if 'shipper_address' not in existing_columns:
        op.add_column('fedex_configurations', sa.Column('shipper_address', sa.Text(), nullable=True))
    if 'shipper_contact' not in existing_columns:
        op.add_column('fedex_configurations', sa.Column('shipper_contact', sa.Text(), nullable=True))
    
    # Add shipment configuration fields
    if 'payment_type' not in existing_columns:
        op.add_column('fedex_configurations', sa.Column('payment_type', sa.String(length=50), nullable=True))
    if 'label_stock_type' not in existing_columns:
        op.add_column('fedex_configurations', sa.Column('label_stock_type', sa.String(length=50), nullable=True))
    if 'label_format_type' not in existing_columns:
        op.add_column('fedex_configurations', sa.Column('label_format_type', sa.String(length=50), nullable=True))
    if 'label_print_type' not in existing_columns:
        op.add_column('fedex_configurations', sa.Column('label_print_type', sa.String(length=50), nullable=True))
    
    # Change account_number from INTEGER to String (only if it's still INTEGER)
    if 'account_number' in existing_columns:
        account_col = next((col for col in inspector.get_columns('fedex_configurations') if col['name'] == 'account_number'), None)
        if account_col and 'INT' in str(account_col['type']).upper():
            op.alter_column('fedex_configurations', 'account_number',
                       existing_type=mysql.INTEGER(),
                       type_=sa.String(length=50),
                       existing_nullable=True)
    
    # Change default_weight from INTEGER to Numeric(10, 2) (only if it's still INTEGER)
    if 'default_weight' in existing_columns:
        weight_col = next((col for col in inspector.get_columns('fedex_configurations') if col['name'] == 'default_weight'), None)
        if weight_col and 'INT' in str(weight_col['type']).upper():
            op.alter_column('fedex_configurations', 'default_weight',
                       existing_type=mysql.INTEGER(),
                       type_=sa.Numeric(precision=10, scale=2),
                       existing_nullable=True)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### FedEx Configuration rollback only ###
    # Revert default_weight from Numeric(10, 2) to INTEGER
    op.alter_column('fedex_configurations', 'default_weight',
               existing_type=sa.Numeric(precision=10, scale=2),
               type_=mysql.INTEGER(),
               existing_nullable=True)
    
    # Revert account_number from String(50) to INTEGER
    op.alter_column('fedex_configurations', 'account_number',
               existing_type=sa.String(length=50),
               type_=mysql.INTEGER(),
               existing_nullable=True)
    
    # Drop added columns
    op.drop_column('fedex_configurations', 'label_print_type')
    op.drop_column('fedex_configurations', 'label_format_type')
    op.drop_column('fedex_configurations', 'label_stock_type')
    op.drop_column('fedex_configurations', 'payment_type')
    op.drop_column('fedex_configurations', 'shipper_contact')
    op.drop_column('fedex_configurations', 'shipper_address')
    op.drop_column('fedex_configurations', 'child_secret')
    op.drop_column('fedex_configurations', 'child_key')
    op.drop_column('fedex_configurations', 'grant_type')
    # ### end Alembic commands ###
