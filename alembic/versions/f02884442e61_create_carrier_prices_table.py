"""create_carrier_prices_table

Revision ID: f02884442e61
Revises: 68c4974dd16f
Create Date: 2025-11-28 11:59:28.971153

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f02884442e61'
down_revision: Union[str, None] = '68c4974dd16f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Crea la tabella carrier_prices per gestione prezzi corrieri."""
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    existing_tables = inspector.get_table_names()
    
    if 'carrier_prices' not in existing_tables:
        op.create_table(
            'carrier_prices',
            sa.Column('id_carrier_price', sa.Integer(), nullable=False),
            sa.Column('id_carrier_api', sa.Integer(), nullable=False),
            sa.Column('postal_codes', sa.String(1000), nullable=True),
            sa.Column('countries', sa.String(1000), nullable=True),
            sa.Column('min_weight', sa.Numeric(10, 5), nullable=True),
            sa.Column('max_weight', sa.Numeric(10, 5), nullable=True),
            sa.Column('price_with_tax', sa.Numeric(10, 5), nullable=True),
            sa.ForeignKeyConstraint(['id_carrier_api'], ['carriers_api.id_carrier_api'], ),
            sa.PrimaryKeyConstraint('id_carrier_price'),
            sa.Index('ix_carrier_prices_id_carrier_price', 'id_carrier_price'),
            sa.Index('ix_carrier_prices_id_carrier_api', 'id_carrier_api')
        )
        print("Successfully created carrier_prices table")
    else:
        print("WARNING: carrier_prices table already exists")


def downgrade() -> None:
    """Elimina la tabella carrier_prices."""
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    existing_tables = inspector.get_table_names()
    
    if 'carrier_prices' in existing_tables:
        op.drop_table('carrier_prices')
        print("Successfully dropped carrier_prices table")
    else:
        print("WARNING: carrier_prices table does not exist")
