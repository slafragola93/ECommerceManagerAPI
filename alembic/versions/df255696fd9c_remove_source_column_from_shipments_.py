"""remove source column from shipments_history

Revision ID: df255696fd9c
Revises: 349dfd185497
Create Date: 2026-01-15 08:48:52.432551

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'df255696fd9c'
down_revision: Union[str, None] = '349dfd185497'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Rimuovi la colonna source dalla tabella shipments_history
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    # Verifica se la colonna esiste prima di rimuoverla
    columns = [col['name'] for col in inspector.get_columns('shipments_history')]
    if 'source' in columns:
        op.drop_column('shipments_history', 'source')


def downgrade() -> None:
    # Ripristina la colonna source (come VARCHAR per compatibilità)
    try:
        op.add_column('shipments_history', sa.Column('source', sa.String(length=20), nullable=True))
    except Exception:
        # Se la colonna esiste già, ignora l'errore
        pass
