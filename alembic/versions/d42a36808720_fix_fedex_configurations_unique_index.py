"""fix_fedex_configurations_unique_index

Revision ID: d42a36808720
Revises: a968bc3bc78f
Create Date: 2026-01-13 12:00:25.143072

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd42a36808720'
down_revision: Union[str, None] = 'a968bc3bc78f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Rimuove l'indice unique su id_carrier_api se esiste ancora.
    Questo permette di avere multiple configurazioni FedEx per lo stesso id_carrier_api
    con scope diversi (SHIP, TRACK).
    """
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    # Ottieni tutti gli indici sulla tabella
    indexes = inspector.get_indexes('fedex_configurations')
    
    # Cerca l'indice su id_carrier_api
    for idx in indexes:
        if idx['name'] == 'ix_fedex_configurations_id_carrier_api':
            # Se è unique, rimuovilo
            if idx.get('unique', False):
                try:
                    # Prova a rimuoverlo come constraint unique
                    op.drop_constraint('ix_fedex_configurations_id_carrier_api', 'fedex_configurations', type_='unique')
                except Exception:
                    try:
                        # Se fallisce, prova a rimuoverlo come indice
                        op.drop_index('ix_fedex_configurations_id_carrier_api', table_name='fedex_configurations')
                    except Exception:
                        # Se anche questo fallisce, prova con op.f()
                        try:
                            op.drop_index(op.f('ix_fedex_configurations_id_carrier_api'), table_name='fedex_configurations')
                        except Exception as e:
                            # Log ma continua
                            print(f"Warning: Could not drop index: {e}")
            
            # Ricrea l'indice come non-unique se non esiste già
            current_indexes = [i['name'] for i in inspector.get_indexes('fedex_configurations')]
            if 'ix_fedex_configurations_id_carrier_api' not in current_indexes:
                op.create_index(
                    op.f('ix_fedex_configurations_id_carrier_api'),
                    'fedex_configurations',
                    ['id_carrier_api'],
                    unique=False
                )
            break


def downgrade() -> None:
    """
    Ripristina l'indice unique su id_carrier_api (per rollback)
    """
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    # Rimuovi l'indice non-unique se esiste
    indexes = [idx['name'] for idx in inspector.get_indexes('fedex_configurations')]
    if 'ix_fedex_configurations_id_carrier_api' in indexes:
        try:
            op.drop_index(op.f('ix_fedex_configurations_id_carrier_api'), table_name='fedex_configurations')
        except Exception:
            pass
    
    # Ricrea come unique
    op.create_index(
        op.f('ix_fedex_configurations_id_carrier_api'),
        'fedex_configurations',
        ['id_carrier_api'],
        unique=True
    )
