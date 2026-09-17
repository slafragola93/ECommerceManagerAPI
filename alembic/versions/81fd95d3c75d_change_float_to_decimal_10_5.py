"""change_float_to_decimal_10_5

Revision ID: 81fd95d3c75d
Revises: e862e0593f66
Create Date: 2025-11-07 15:55:44.195650

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '81fd95d3c75d'
down_revision: Union[str, None] = 'e862e0593f66'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Modifica tutte le colonne Float in DECIMAL(10,5) per supportare 5 decimali durante import/creazione.
    """
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    # Lista di tutte le modifiche: (tabella, colonna, nullable, default)
    changes = [
        # products
        ('products', 'weight', False, '0.0'),
        ('products', 'depth', False, '0.0'),
        ('products', 'height', False, '0.0'),
        ('products', 'width', False, '0.0'),
        ('products', 'price_without_tax', True, '0.0'),
        ('products', 'purchase_price', True, '0.0'),
        
        # order_details
        ('order_details', 'product_weight', False, None),
        ('order_details', 'product_price', False, None),
        ('order_details', 'reduction_percent', False, '0.0'),
        ('order_details', 'reduction_amount', False, '0.0'),
        
        # orders
        ('orders', 'total_weight', False, '0'),
        ('orders', 'total_price_tax_excl', False, '0'),
        ('orders', 'total_paid', False, '0'),
        ('orders', 'total_discounts', False, '0.0'),
        ('orders', 'cash_on_delivery', False, '0'),
        ('orders', 'insured_value', False, '0'),
        
        # orders_document
        ('orders_document', 'total_weight', False, None),
        ('orders_document', 'total_price_with_tax', False, None),
        ('orders_document', 'total_discount', False, '0.0'),
        
        # order_packages
        ('order_packages', 'height', False, None),
        ('order_packages', 'width', False, None),
        ('order_packages', 'depth', False, None),
        ('order_packages', 'length', False, None),
        ('order_packages', 'weight', False, None),
        ('order_packages', 'value', False, '0.0'),
        
        # shipments
        ('shipments', 'weight', False, '0'),
        ('shipments', 'price_tax_incl', False, '0'),
        ('shipments', 'price_tax_excl', False, '0'),
        
        # carrier_assignments
        ('carrier_assignments', 'min_weight', True, None),
        ('carrier_assignments', 'max_weight', True, None),
        
        # fiscal_document_details
        ('fiscal_document_details', 'quantity', False, None),
        ('fiscal_document_details', 'unit_price', False, None),
        ('fiscal_document_details', 'total_amount', False, None),
        
        # fiscal_documents
        ('fiscal_documents', 'total_amount', True, None),
    ]
    
    for table_name, column_name, nullable, default in changes:
        # Verifica che la tabella esista
        if table_name not in inspector.get_table_names():
            print(f"WARNING: Table {table_name} does not exist, skipping {column_name}")
            continue
        
        # Verifica che la colonna esista
        columns = {col['name']: col for col in inspector.get_columns(table_name)}
        if column_name not in columns:
            print(f"WARNING: Column {column_name} does not exist in {table_name}, skipping")
            continue
        
        # Ottieni il tipo corrente
        current_type = str(columns[column_name]['type']).upper()
        
        # Se è già DECIMAL/NUMERIC, verifica se è (10,5)
        if 'DECIMAL' in current_type or 'NUMERIC' in current_type:
            if '10,5' in current_type or '(10,5)' in current_type:
                print(f"INFO: Column {table_name}.{column_name} is already DECIMAL(10,5), skipping")
                continue
        
        try:
            # Prepara i parametri per alter_column
            alter_params = {
                'table_name': table_name,
                'column_name': column_name,
                'existing_type': sa.Float(),
                'type_': sa.Numeric(10, 5),
                'existing_nullable': nullable,
                'nullable': nullable
            }
            
            # Aggiungi default se specificato
            if default is not None:
                alter_params['server_default'] = sa.text(default)
                alter_params['existing_server_default'] = sa.text(default) if default else None
            
            op.alter_column(**alter_params)
            print(f"SUCCESS: Changed {table_name}.{column_name} from Float to DECIMAL(10,5)")
        except Exception as e:
            print(f"ERROR: Could not alter {table_name}.{column_name}: {e}")
            # Continua con le altre colonne anche se una fallisce


def downgrade() -> None:
    """
    Ripristina tutte le colonne DECIMAL(10,5) a Float.
    """
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    # Lista di tutte le modifiche: (tabella, colonna, nullable, default)
    changes = [
        # products
        ('products', 'weight', False, '0.0'),
        ('products', 'depth', False, '0.0'),
        ('products', 'height', False, '0.0'),
        ('products', 'width', False, '0.0'),
        ('products', 'price_without_tax', True, '0.0'),
        ('products', 'purchase_price', True, '0.0'),
        
        # order_details
        ('order_details', 'product_weight', False, None),
        ('order_details', 'product_price', False, None),
        ('order_details', 'reduction_percent', False, '0.0'),
        ('order_details', 'reduction_amount', False, '0.0'),
        
        # orders
        ('orders', 'total_weight', False, '0'),
        ('orders', 'total_price_tax_excl', False, '0'),
        ('orders', 'total_paid', False, '0'),
        ('orders', 'total_discounts', False, '0.0'),
        ('orders', 'cash_on_delivery', False, '0'),
        ('orders', 'insured_value', False, '0'),
        
        # orders_document
        ('orders_document', 'total_weight', False, None),
        ('orders_document', 'total_price_with_tax', False, None),
        ('orders_document', 'total_discount', False, '0.0'),
        
        # order_packages
        ('order_packages', 'height', False, None),
        ('order_packages', 'width', False, None),
        ('order_packages', 'depth', False, None),
        ('order_packages', 'length', False, None),
        ('order_packages', 'weight', False, None),
        ('order_packages', 'value', False, '0.0'),
        
        # shipments
        ('shipments', 'weight', False, '0'),
        ('shipments', 'price_tax_incl', False, '0'),
        ('shipments', 'price_tax_excl', False, '0'),
        
        # carrier_assignments
        ('carrier_assignments', 'min_weight', True, None),
        ('carrier_assignments', 'max_weight', True, None),
        
        # fiscal_document_details
        ('fiscal_document_details', 'quantity', False, None),
        ('fiscal_document_details', 'unit_price', False, None),
        ('fiscal_document_details', 'total_amount', False, None),
        
        # fiscal_documents
        ('fiscal_documents', 'total_amount', True, None),
    ]
    
    for table_name, column_name, nullable, default in changes:
        # Verifica che la tabella esista
        if table_name not in inspector.get_table_names():
            print(f"WARNING: Table {table_name} does not exist, skipping {column_name}")
            continue
        
        # Verifica che la colonna esista
        columns = {col['name']: col for col in inspector.get_columns(table_name)}
        if column_name not in columns:
            print(f"WARNING: Column {column_name} does not exist in {table_name}, skipping")
            continue
        
        try:
            # Prepara i parametri per alter_column
            alter_params = {
                'table_name': table_name,
                'column_name': column_name,
                'existing_type': sa.Numeric(10, 5),
                'type_': sa.Float(),
                'existing_nullable': nullable,
                'nullable': nullable
            }
            
            # Aggiungi default se specificato
            if default is not None:
                alter_params['server_default'] = sa.text(default)
                alter_params['existing_server_default'] = sa.text(default) if default else None
            
            op.alter_column(**alter_params)
            print(f"SUCCESS: Changed {table_name}.{column_name} from DECIMAL(10,5) to Float")
        except Exception as e:
            print(f"ERROR: Could not alter {table_name}.{column_name}: {e}")
            # Continua con le altre colonne anche se una fallisce
