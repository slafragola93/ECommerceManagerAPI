"""consolidated_initial_migration

Revision ID: 5c44d2400e1d
Revises: 
Create Date: 2025-10-23 15:39:55.364164

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5c44d2400e1d'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Consolidated migration - create all tables with current structure"""
    from alembic import context
    conn = context.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()
    
    # Create carrier_api table
    if 'carriers_api' not in existing_tables:
        op.create_table('carriers_api',
            sa.Column('id_carrier_api', sa.Integer(), nullable=False),
            sa.Column('id_carrier', sa.Integer(), nullable=False),
            sa.Column('carrier_type', sa.Enum('BRT', 'DHL', 'FEDEX', name='carriertypeenum'), nullable=False),
            sa.Column('api_username', sa.String(255), nullable=True),
            sa.Column('api_password', sa.String(255), nullable=True),
            sa.Column('api_key', sa.String(500), nullable=True),
            sa.Column('base_url', sa.String(500), nullable=True),
            sa.Column('use_sandbox', sa.Boolean(), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['id_carrier'], ['carriers.id_carrier'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id_carrier_api')
        )
        
    if 'dhl_configurations' not in existing_tables:
        # Create DHL configurations table with current structure
        op.create_table('dhl_configurations',
            sa.Column('id_dhl_config', sa.Integer(), nullable=False),
            sa.Column('id_carrier_api', sa.Integer(), nullable=False),
            sa.Column('description', sa.String(255), nullable=False),
            sa.Column('shipper_account_number', sa.String(255), nullable=False),
            sa.Column('company_name', sa.String(255), nullable=False),
            sa.Column('city', sa.String(100), nullable=False),
            sa.Column('address', sa.String(255), nullable=False),
            sa.Column('postal_code', sa.String(20), nullable=False),
            sa.Column('country_code', sa.String(2), nullable=False),
            sa.Column('reference_person', sa.String(255), nullable=False),
            sa.Column('email', sa.String(255), nullable=False),
            sa.Column('phone', sa.String(50), nullable=False),
            sa.Column('default_weight', sa.Numeric(10, 2), nullable=False),
            sa.Column('package_height', sa.Integer(), nullable=False),
            sa.Column('package_width', sa.Integer(), nullable=False),
            sa.Column('package_depth', sa.Integer(), nullable=False),
            sa.Column('goods_description', sa.Text(), nullable=True),
            sa.Column('label_format', sa.Enum('PDF', 'ZPL', name='labelformatenum'), nullable=False),
            sa.Column('unit_of_measure', sa.Enum('Metric', 'Imperial', name='unitofmeasureenum'), nullable=False),
            sa.Column('default_is_customs_declarable', sa.Boolean(), nullable=False),
            sa.Column('default_incoterm', sa.String(3), nullable=True),
            sa.Column('duties_account_number', sa.String(255), nullable=True),
            sa.Column('payer_account_number', sa.String(255), nullable=True),
            sa.Column('province_code', sa.String(50), nullable=True),
            sa.Column('tax_id', sa.String(255), nullable=True),
            sa.Column('pickup_is_requested', sa.Boolean(), nullable=False),
            sa.Column('pickup_close_time', sa.String(5), nullable=True),
            sa.Column('pickup_location', sa.String(255), nullable=True),
            sa.Column('default_product_code_domestic', sa.String(100), nullable=False),
            sa.Column('default_product_code_international', sa.String(100), nullable=False),
            sa.Column('cod_enabled', sa.Boolean(), nullable=False),
            sa.Column('cod_currency', sa.String(3), nullable=True),
            sa.ForeignKeyConstraint(['id_carrier_api'], ['carriers_api.id_carrier_api'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id_dhl_config'),
            sa.UniqueConstraint('id_carrier_api')
        )
    
    if 'shipment_requests' not in existing_tables:
    # Create shipment_requests table
        op.create_table('shipment_requests',
            sa.Column('id_shipment_request', sa.Integer(), nullable=False),
            sa.Column('order_id', sa.Integer(), nullable=False),
            sa.Column('carrier_api_id', sa.Integer(), nullable=False),
            sa.Column('awb', sa.String(100), nullable=True),
            sa.Column('message_reference', sa.String(100), nullable=False),
            sa.Column('environment', sa.Enum('SANDBOX', 'PRODUCTION', name='environmentenum'), nullable=False),
            sa.Column('request_payload', sa.JSON(), nullable=True),
            sa.Column('response_payload', sa.JSON(), nullable=True),
            sa.Column('status', sa.String(50), nullable=False),
            sa.Column('error_message', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.Column('expires_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id_shipment_request'),
            sa.UniqueConstraint('message_reference')
        )
    
    if 'shipment_documents' not in existing_tables:
        # Create shipment_documents table
        op.create_table('shipment_documents',
            sa.Column('id_shipment_document', sa.Integer(), nullable=False),
            sa.Column('shipment_request_id', sa.Integer(), nullable=False),
            sa.Column('document_type', sa.String(50), nullable=False),
            sa.Column('file_path', sa.String(500), nullable=False),
            sa.Column('file_size', sa.Integer(), nullable=True),
            sa.Column('mime_type', sa.String(100), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('expires_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['shipment_request_id'], ['shipment_requests.id_shipment_request'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id_shipment_document')
        )
    
    if 'shipments_history' not in existing_tables:
        # Create shipments_history table
        op.create_table('shipments_history',
            sa.Column('id_shipment_history', sa.Integer(), nullable=False),
            sa.Column('order_id', sa.Integer(), nullable=False),
            sa.Column('awb', sa.String(100), nullable=False),
            sa.Column('carrier', sa.String(50), nullable=False),
            sa.Column('status', sa.String(50), nullable=False),
            sa.Column('tracking_data', sa.JSON(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id_shipment_history')
        )


def downgrade() -> None:
    """Drop all tables in reverse order"""
    op.drop_table('shipments_history')
    op.drop_table('shipment_documents')
    op.drop_table('shipment_requests')
    op.drop_table('dhl_configurations')
    op.drop_table('carriers_api')
    op.drop_table('carriers')
    op.drop_table('app_configurations')
