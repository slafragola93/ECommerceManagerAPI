"""add_scope_to_fedex_configurations

Revision ID: a968bc3bc78f
Revises: f63a17e8104d
Create Date: 2026-01-13 10:43:24.980450

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a968bc3bc78f'
down_revision: Union[str, None] = 'f63a17e8104d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Step 1: Rimuovere il vincolo unique da id_carrier_api
    # In MySQL, un indice unique è un constraint, quindi proviamo a rimuoverlo come constraint
    # Se non funziona, proviamo come indice
    try:
        op.drop_constraint('ix_fedex_configurations_id_carrier_api', 'fedex_configurations', type_='unique')
    except Exception:
        try:
            op.drop_index(op.f('ix_fedex_configurations_id_carrier_api'), table_name='fedex_configurations')
        except Exception:
            try:
                op.drop_index('id_carrier_api', table_name='fedex_configurations')
            except Exception:
                # Se tutti i tentativi falliscono, l'indice potrebbe non esistere
                # Procediamo comunque
                pass
    
    # Step 2: Aggiungere la colonna scope con default 'SHIP' (se non esiste già)
    # Verifichiamo se la colonna esiste già
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    columns = [col['name'] for col in inspector.get_columns('fedex_configurations')]
    
    if 'scope' not in columns:
        op.add_column('fedex_configurations', 
                      sa.Column('scope', sa.Enum('SHIP', 'TRACK', name='fedexscopeenum'), 
                               nullable=False, server_default='SHIP'))
    
    # Step 3: Verificare se l'indice esiste ancora, se sì rimuoverlo e ricrearlo senza unique
    # Se non esiste, crearlo
    indexes = [idx['name'] for idx in inspector.get_indexes('fedex_configurations')]
    if 'ix_fedex_configurations_id_carrier_api' in indexes:
        try:
            op.drop_index(op.f('ix_fedex_configurations_id_carrier_api'), table_name='fedex_configurations')
        except Exception:
            pass
    
    # Ricreare l'indice solo se non esiste già
    if 'ix_fedex_configurations_id_carrier_api' not in [idx['name'] for idx in inspector.get_indexes('fedex_configurations')]:
        op.create_index(op.f('ix_fedex_configurations_id_carrier_api'), 'fedex_configurations', ['id_carrier_api'], unique=False)
    
    # Step 4: Aggiungere indice unico composto su (id_carrier_api, scope)
    op.create_unique_constraint('uq_fedex_config_carrier_scope', 'fedex_configurations', 
                                ['id_carrier_api', 'scope'])


def downgrade() -> None:
    # Step 1: Rimuovere l'indice unico composto
    op.drop_constraint('uq_fedex_config_carrier_scope', 'fedex_configurations', type_='unique')
    
    # Step 2: Rimuovere l'indice non-unique su id_carrier_api
    op.drop_index(op.f('ix_fedex_configurations_id_carrier_api'), table_name='fedex_configurations')
    
    # Step 3: Rimuovere la colonna scope
    op.drop_column('fedex_configurations', 'scope')
    
    # Step 4: Ricreare il vincolo unique su id_carrier_api
    op.create_index(op.f('ix_fedex_configurations_id_carrier_api'), 'fedex_configurations', ['id_carrier_api'], unique=True)
