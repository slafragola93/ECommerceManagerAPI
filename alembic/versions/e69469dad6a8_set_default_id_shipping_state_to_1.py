"""set_default_id_shipping_state_to_1

Revision ID: e69469dad6a8
Revises: d2e80f84ce12
Create Date: 2026-01-20 11:47:13.390144

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = 'e69469dad6a8'
down_revision: Union[str, None] = 'd2e80f84ce12'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()
    
    # Verifica se la colonna esiste
    result = connection.execute(text("""
        SELECT COUNT(*) as count
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
        AND TABLE_NAME = 'shipments'
        AND COLUMN_NAME = 'id_shipping_state'
    """))
    column_exists = result.fetchone()[0] > 0
    
    if column_exists:
        # Aggiorna tutti i valori NULL esistenti a 1
        connection.execute(text("""
            UPDATE shipments
            SET id_shipping_state = 1
            WHERE id_shipping_state IS NULL
        """))
        
        # Modifica la colonna per avere default=1 e nullable=False
        op.alter_column('shipments', 'id_shipping_state',
                       existing_type=sa.Integer(),
                       nullable=False,
                       server_default='1')
        print("SUCCESS: Set default id_shipping_state to 1 in shipments table")
    else:
        print("WARNING: Column id_shipping_state does not exist in shipments table")


def downgrade() -> None:
    connection = op.get_bind()
    
    # Verifica se la colonna esiste
    result = connection.execute(text("""
        SELECT COUNT(*) as count
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
        AND TABLE_NAME = 'shipments'
        AND COLUMN_NAME = 'id_shipping_state'
    """))
    column_exists = result.fetchone()[0] > 0
    
    if column_exists:
        # Ripristina la colonna a nullable con default None
        op.alter_column('shipments', 'id_shipping_state',
                       existing_type=sa.Integer(),
                       nullable=True,
                       server_default=None)
        print("SUCCESS: Reverted id_shipping_state to nullable with no default")
    else:
        print("WARNING: Column id_shipping_state does not exist in shipments table")
