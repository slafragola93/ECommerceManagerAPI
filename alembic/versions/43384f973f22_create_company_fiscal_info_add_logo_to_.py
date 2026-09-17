"""create_company_fiscal_info_add_logo_to_store

Revision ID: 43384f973f22
Revises: 930bc8cbac0f
Create Date: 2025-12-12 17:25:36.980674

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '43384f973f22'
down_revision: Union[str, None] = '930bc8cbac0f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Crea tabella company_fiscal_info
    op.create_table(
        'company_fiscal_info',
        sa.Column('id_company_fiscal_info', sa.Integer(), nullable=False),
        sa.Column('id_store', sa.Integer(), nullable=False),
        sa.Column('company_name', sa.String(length=200), nullable=False),
        sa.Column('vat_number', sa.String(length=50), nullable=False),
        sa.Column('fiscal_code', sa.String(length=50), nullable=True),
        sa.Column('rea_number', sa.String(length=50), nullable=True),
        sa.Column('address', sa.String(length=255), nullable=True),
        sa.Column('postal_code', sa.String(length=20), nullable=True),
        sa.Column('city', sa.String(length=100), nullable=True),
        sa.Column('province', sa.String(length=10), nullable=True),
        sa.Column('country', sa.String(length=5), nullable=True),
        sa.Column('phone', sa.String(length=50), nullable=True),
        sa.Column('fax', sa.String(length=50), nullable=True),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('pec', sa.String(length=255), nullable=True),
        sa.Column('sdi_code', sa.String(length=50), nullable=True),
        sa.Column('bank_name', sa.String(length=200), nullable=True),
        sa.Column('iban', sa.String(length=50), nullable=True),
        sa.Column('bic_swift', sa.String(length=20), nullable=True),
        sa.Column('abi', sa.String(length=10), nullable=True),
        sa.Column('cab', sa.String(length=10), nullable=True),
        sa.Column('account_holder', sa.String(length=200), nullable=True),
        sa.Column('account_number', sa.String(length=50), nullable=True),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('date_add', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id_company_fiscal_info'),
        sa.ForeignKeyConstraint(['id_store'], ['stores.id_store'], ondelete='CASCADE')
    )
    
    # Crea indice su id_store
    op.create_index(op.f('ix_company_fiscal_info_id_store'), 'company_fiscal_info', ['id_store'], unique=False)
    
    # Crea indice su vat_number
    op.create_index(op.f('ix_company_fiscal_info_vat_number'), 'company_fiscal_info', ['vat_number'], unique=False)
    
    # Aggiungi colonna logo alla tabella stores
    op.add_column('stores', sa.Column('logo', sa.String(length=500), nullable=True))


def downgrade() -> None:
    # Rimuovi colonna logo dalla tabella stores
    op.drop_column('stores', 'logo')
    
    # Rimuovi indici
    op.drop_index(op.f('ix_company_fiscal_info_vat_number'), table_name='company_fiscal_info')
    op.drop_index(op.f('ix_company_fiscal_info_id_store'), table_name='company_fiscal_info')
    
    # Rimuovi tabella company_fiscal_info
    op.drop_table('company_fiscal_info')
