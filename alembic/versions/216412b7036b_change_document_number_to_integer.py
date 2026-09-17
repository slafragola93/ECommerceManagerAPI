"""change_document_number_to_integer

Revision ID: 216412b7036b
Revises: b3ba1b4f2909
Create Date: 2025-11-04 17:17:07.596145

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '216412b7036b'
down_revision: Union[str, None] = 'b3ba1b4f2909'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Converte la colonna document_number da VARCHAR(32) a INTEGER nella tabella orders_document.
    
    Prima converte tutti i valori stringa validi a intero, poi modifica il tipo di colonna.
    I valori non convertibili vengono impostati a NULL.
    """
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    # Verifica che la colonna esista
    columns = {col['name']: col for col in inspector.get_columns('orders_document')}
    if 'document_number' not in columns:
        print("WARNING: Column document_number not found in orders_document table")
        return
    
    # Ottieni il tipo corrente
    current_type = str(columns['document_number']['type']).upper()
    
    # Se è già INTEGER, non fare nulla
    if 'INT' in current_type:
        print("INFO: Column document_number is already INTEGER, skipping conversion")
        return
    
    # Step 1: Converti i valori stringa validi a intero
    # Prima aggiorna i valori che possono essere convertiti
    print("Converting string document_number values to integers...")
    op.execute(sa.text("""
        UPDATE orders_document 
        SET document_number = CAST(document_number AS UNSIGNED)
        WHERE document_number REGEXP '^[0-9]+$' 
        AND document_number IS NOT NULL
        AND document_number != ''
    """))
    
    # Step 2: Imposta a NULL i valori non convertibili (non numerici)
    op.execute(sa.text("""
        UPDATE orders_document 
        SET document_number = NULL
        WHERE document_number IS NOT NULL 
        AND document_number NOT REGEXP '^[0-9]+$'
    """))
    
    # Step 3: Cambia il tipo di colonna da VARCHAR a INTEGER
    # MySQL richiede di specificare existing_type per ALTER COLUMN
    print("Changing column type from VARCHAR to INTEGER...")
    op.alter_column(
        'orders_document',
        'document_number',
        existing_type=sa.String(32),
        type_=sa.Integer(),
        nullable=True,
        existing_nullable=True
    )
    
    print("Successfully converted document_number from VARCHAR to INTEGER")


def downgrade() -> None:
    """
    Ripristina la colonna document_number da INTEGER a VARCHAR(32).
    """
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    # Verifica che la colonna esista
    columns = {col['name']: col for col in inspector.get_columns('orders_document')}
    if 'document_number' not in columns:
        print("WARNING: Column document_number not found in orders_document table")
        return
    
    # Ottieni il tipo corrente
    current_type = str(columns['document_number']['type']).upper()
    
    # Se è già VARCHAR, non fare nulla
    if 'VARCHAR' in current_type or 'STRING' in current_type:
        print("INFO: Column document_number is already VARCHAR, skipping conversion")
        return
    
    # Cambia il tipo di colonna da INTEGER a VARCHAR(32)
    print("Changing column type from INTEGER to VARCHAR...")
    op.alter_column(
        'orders_document',
        'document_number',
        existing_type=sa.Integer(),
        type_=sa.String(32),
        nullable=True,
        existing_nullable=True
    )
    
    # Converte i valori interi a stringa
    op.execute(sa.text("""
        UPDATE orders_document 
        SET document_number = CAST(document_number AS CHAR)
        WHERE document_number IS NOT NULL
    """))
    
    print("Successfully converted document_number from INTEGER to VARCHAR")
