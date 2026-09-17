"""remove_api_key_from_carriers_api

Revision ID: 6a5e4a6b1f3b
Revises: 4758c3229ba1
Create Date: 2026-01-27 11:31:22.277043

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6a5e4a6b1f3b'
down_revision: Union[str, None] = '4758c3229ba1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)

    if 'carriers_api' in inspector.get_table_names():
        columns = [col['name'] for col in inspector.get_columns('carriers_api')]
        if 'api_key' in columns:
            op.drop_column('carriers_api', 'api_key')   

def downgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)

    if 'carriers_api' in inspector.get_table_names():
        columns = [col['name'] for col in inspector.get_columns('carriers_api')]
        if 'api_key' not in columns:
            op.add_column('carriers_api', sa.Column('api_key', sa.String(200), nullable=True))
