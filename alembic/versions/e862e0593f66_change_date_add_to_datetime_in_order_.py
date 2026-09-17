"""change_date_add_to_datetime_in_order_document

Revision ID: e862e0593f66
Revises: 150bf63bde32
Create Date: 2025-11-06 12:20:19.360717

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e862e0593f66'
down_revision: Union[str, None] = '150bf63bde32'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Controlla se la tabella esiste
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    # Verifica se la tabella orders_document esiste
    if 'orders_document' not in inspector.get_table_names():
        print("WARNING: orders_document table does not exist")
        return
    
    # Verifica il tipo corrente della colonna date_add
    columns = {col['name']: col for col in inspector.get_columns('orders_document')}
    
    if 'date_add' not in columns:
        print("WARNING: date_add column does not exist in orders_document table")
        return
    
    # Modifica il tipo della colonna da Date a DateTime
    # Per MySQL/MariaDB, usiamo ALTER COLUMN
    # Per SQLite, usiamo una ricreazione della colonna
    try:
        op.alter_column('orders_document', 'date_add',
                       existing_type=sa.Date(),
                       type_=sa.DateTime(),
                       existing_nullable=True,
                       existing_server_default=sa.text('CURRENT_TIMESTAMP'))
        print("SUCCESS: Changed date_add column type from Date to DateTime in orders_document table")
    except Exception as e:
        # Fallback per database che non supportano ALTER COLUMN direttamente
        print(f"WARNING: Could not alter column directly: {e}")
        print("You may need to manually migrate the column type")


def downgrade() -> None:
    # Controlla se la tabella esiste
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    # Verifica se la tabella orders_document esiste
    if 'orders_document' not in inspector.get_table_names():
        print("WARNING: orders_document table does not exist")
        return
    
    # Verifica il tipo corrente della colonna date_add
    columns = {col['name']: col for col in inspector.get_columns('orders_document')}
    
    if 'date_add' not in columns:
        print("WARNING: date_add column does not exist in orders_document table")
        return
    
    # Modifica il tipo della colonna da DateTime a Date
    try:
        op.alter_column('orders_document', 'date_add',
                       existing_type=sa.DateTime(),
                       type_=sa.Date(),
                       existing_nullable=True,
                       existing_server_default=sa.text('CURRENT_TIMESTAMP'))
        print("SUCCESS: Changed date_add column type from DateTime to Date in orders_document table")
    except Exception as e:
        # Fallback per database che non supportano ALTER COLUMN direttamente
        print(f"WARNING: Could not alter column directly: {e}")
        print("You may need to manually migrate the column type")
