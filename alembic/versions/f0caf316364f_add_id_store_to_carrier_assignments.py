"""add_id_store_to_carrier_assignments

Revision ID: f0caf316364f
Revises: 43384f973f22
Create Date: 2025-12-15 09:06:16.940267

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f0caf316364f'
down_revision: Union[str, None] = '43384f973f22'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Aggiungi colonna id_store alla tabella carrier_assignments
    op.add_column('carrier_assignments', sa.Column('id_store', sa.Integer(), nullable=True))
    
    # Crea foreign key
    op.create_foreign_key(
        'fk_carrier_assignments_store',
        'carrier_assignments',
        'stores',
        ['id_store'],
        ['id_store'],
        ondelete='SET NULL'
    )
    
    # Crea indice
    op.create_index(
        op.f('ix_carrier_assignments_id_store'),
        'carrier_assignments',
        ['id_store'],
        unique=False
    )


def downgrade() -> None:
    # Rimuovi indice
    op.drop_index(op.f('ix_carrier_assignments_id_store'), table_name='carrier_assignments')
    
    # Rimuovi foreign key
    op.drop_constraint('fk_carrier_assignments_store', 'carrier_assignments', type_='foreignkey')
    
    # Rimuovi colonna
    op.drop_column('carrier_assignments', 'id_store')
