"""Drop FK da tabella products

Revision ID: 0ffd07cd7fd1
Revises: fcff1c3ca694
Create Date: 2024-04-08 15:57:21.333389

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0ffd07cd7fd1'
down_revision: Union[str, None] = 'fcff1c3ca694'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint('products_ibfk_1', 'products', type_='foreignkey')
    op.drop_constraint('products_ibfk_2', 'products', type_='foreignkey')


def downgrade() -> None:
    op.create_foreign_key('products_ibfk_1', 'products', 'categories', ['id_category'], ['id_category'])
    op.create_foreign_key('products_ibfk_2', 'products', 'brands', ['id_brand'], ['id_brand'])
