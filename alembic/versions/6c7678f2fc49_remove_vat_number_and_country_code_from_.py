"""remove_vat_number_and_country_code_from_stores

Revision ID: 6c7678f2fc49
Revises: d42a36808720
Create Date: 2026-01-13 15:26:58.149575

"""
from typing import Sequence, Union
from datetime import datetime

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6c7678f2fc49'
down_revision: Union[str, None] = 'd42a36808720'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Migra vat_number e country_code da stores a company_fiscal_info,
    poi rimuove le colonne da stores.
    """
    connection = op.get_bind()
    
    # 1. Verifica se la tabella company_fiscal_info esiste
    inspector = sa.inspect(connection)
    tables = inspector.get_table_names()
    
    if 'company_fiscal_info' not in tables:
        # Se la tabella non esiste, non possiamo migrare i dati
        # Rimuoviamo solo le colonne
        pass
    else:
        # 2. Migra i dati da stores a company_fiscal_info
        # Per ogni store con vat_number o country_code, crea un CompanyFiscalInfo default
        stores_table = sa.table(
            'stores',
            sa.column('id_store', sa.Integer),
            sa.column('name', sa.String(200)),
            sa.column('vat_number', sa.String(50)),
            sa.column('country_code', sa.String(5))
        )
        
        company_fiscal_info_table = sa.table(
            'company_fiscal_info',
            sa.column('id_company_fiscal_info', sa.Integer),
            sa.column('id_store', sa.Integer),
            sa.column('company_name', sa.String(200)),
            sa.column('vat_number', sa.String(50)),
            sa.column('country', sa.String(5)),
            sa.column('is_default', sa.Boolean),
            sa.column('date_add', sa.DateTime),
            sa.column('updated_at', sa.DateTime)
        )
        
        # Recupera tutti gli store con vat_number o country_code
        result = connection.execute(
            sa.select(stores_table.c.id_store, stores_table.c.vat_number, stores_table.c.country_code)
            .where(
                sa.or_(
                    stores_table.c.vat_number.isnot(None),
                    stores_table.c.country_code.isnot(None)
                )
            )
        )
        
        stores_to_migrate = result.fetchall()
        
        # Per ogni store, crea un CompanyFiscalInfo se non esiste già uno default
        for store_id, vat_number, country_code in stores_to_migrate:
            # Verifica se esiste già un CompanyFiscalInfo default per questo store
            existing = connection.execute(
                sa.select(company_fiscal_info_table.c.id_company_fiscal_info)
                .where(
                    sa.and_(
                        company_fiscal_info_table.c.id_store == store_id,
                        company_fiscal_info_table.c.is_default == True
                    )
                )
            ).first()
            
            if not existing and (vat_number or country_code):
                # Recupera il nome dello store per company_name
                store_name_result = connection.execute(
                    sa.select(stores_table.c.name).where(stores_table.c.id_store == store_id)
                ).first()
                company_name = store_name_result[0] if store_name_result else f"Store {store_id}"
                
                # Crea CompanyFiscalInfo default
                now = datetime.now()
                connection.execute(
                    company_fiscal_info_table.insert().values(
                        id_store=store_id,
                        company_name=company_name,
                        vat_number=vat_number or '',
                        country=country_code,
                        is_default=True,
                        date_add=now,
                        updated_at=now
                    )
                )
    
    # 3. Rimuovi indici se esistono
    try:
        op.drop_index('ix_stores_vat_number', table_name='stores', if_exists=True)
    except Exception:
        pass
    
    try:
        op.drop_index('ix_stores_country_code', table_name='stores', if_exists=True)
    except Exception:
        pass
    
    # 4. Rimuovi colonne
    try:
        op.drop_column('stores', 'vat_number')
    except Exception:
        pass
    
    try:
        op.drop_column('stores', 'country_code')
    except Exception:
        pass


def downgrade() -> None:
    """
    Ripristina le colonne vat_number e country_code in stores
    recuperando i dati da company_fiscal_info (default).
    """
    connection = op.get_bind()
    
    # 1. Aggiungi le colonne
    op.add_column('stores', sa.Column('vat_number', sa.String(50), nullable=True))
    op.add_column('stores', sa.Column('country_code', sa.String(5), nullable=True))
    
    # 2. Crea indici
    op.create_index('ix_stores_vat_number', 'stores', ['vat_number'], unique=False)
    op.create_index('ix_stores_country_code', 'stores', ['country_code'], unique=False)
    
    # 3. Migra i dati da company_fiscal_info (default) a stores
    inspector = sa.inspect(connection)
    tables = inspector.get_table_names()
    
    if 'company_fiscal_info' in tables:
        stores_table = sa.table(
            'stores',
            sa.column('id_store', sa.Integer),
            sa.column('vat_number', sa.String(50)),
            sa.column('country_code', sa.String(5))
        )
        
        company_fiscal_info_table = sa.table(
            'company_fiscal_info',
            sa.column('id_store', sa.Integer),
            sa.column('vat_number', sa.String(50)),
            sa.column('country', sa.String(5))
        )
        
        # Recupera tutti i CompanyFiscalInfo default
        result = connection.execute(
            sa.select(
                company_fiscal_info_table.c.id_store,
                company_fiscal_info_table.c.vat_number,
                company_fiscal_info_table.c.country
            ).where(company_fiscal_info_table.c.is_default == True)
        )
        
        fiscal_infos = result.fetchall()
        
        # Aggiorna stores con i dati da company_fiscal_info
        for store_id, vat_number, country in fiscal_infos:
            connection.execute(
                stores_table.update()
                .where(stores_table.c.id_store == store_id)
                .values(
                    vat_number=vat_number,
                    country_code=country
                )
            )
