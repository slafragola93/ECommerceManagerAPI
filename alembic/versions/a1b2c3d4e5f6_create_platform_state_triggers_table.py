"""create_platform_state_triggers_table

Revision ID: a1b2c3d4e5f6
Revises: 216412b7036b
Create Date: 2025-01-15 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '81fd95d3c75d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Crea la tabella platform_state_triggers per configurazione trigger sincronizzazione stati."""
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    existing_tables = inspector.get_table_names()
    
    if 'platform_state_triggers' not in existing_tables:
        op.create_table(
            'platform_state_triggers',
            sa.Column('id_trigger', sa.Integer(), nullable=False),
            sa.Column('event_type', sa.String(100), nullable=False, comment='Tipo evento (es. order_status_changed, shipping_status_changed)'),
            sa.Column('id_platform', sa.Integer(), nullable=False),
            sa.Column('state_type', sa.String(20), nullable=False, comment='Tipo stato: order_state o shipping_state'),
            sa.Column('id_state_local', sa.Integer(), nullable=False, comment='ID stato locale (OrderState.id_order_state o ShippingState.id_shipping_state)'),
            sa.Column('id_state_platform', sa.Integer(), nullable=False, comment='ID stato sulla piattaforma remota'),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
            sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=True, server_default=sa.func.now(), onupdate=sa.func.now()),
            sa.ForeignKeyConstraint(['id_platform'], ['platforms.id_platform'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id_trigger'),
            sa.Index('idx_event_platform', 'event_type', 'id_platform'),
            sa.Index('idx_state_local', 'state_type', 'id_state_local'),
            sa.Index('idx_active', 'is_active')
        )
        print("Successfully created platform_state_triggers table")


def downgrade() -> None:
    """Elimina la tabella platform_state_triggers."""
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    existing_tables = inspector.get_table_names()
    
    if 'platform_state_triggers' in existing_tables:
        op.drop_table('platform_state_triggers')
        print("Successfully dropped platform_state_triggers table")

