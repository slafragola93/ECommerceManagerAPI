"""add_purchase_price_and_minimal_quantity_to_products

Revision ID: c1b296f48b0d
Revises: df3e3b3684be
Create Date: 2025-11-04 13:09:11.571898
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1b296f48b0d'
down_revision: Union[str, None] = 'df3e3b3684be'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Aggiunge le colonne purchase_price e minimal_quantity alla tabella products.
    Usa i comandi Alembic standard per compatibilità.
    """
    # Ottieni metadati esistenti
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    existing_columns = [col['name'] for col in inspector.get_columns('products')]

    # Aggiungi colonna purchase_price se non esiste
    if 'purchase_price' not in existing_columns:
        op.add_column('products', sa.Column('purchase_price', sa.Float(), nullable=True))
        op.execute(sa.text("UPDATE products SET purchase_price = 0.0 WHERE purchase_price IS NULL"))

    # Aggiungi colonna minimal_quantity se non esiste
    if 'minimal_quantity' not in existing_columns:
        op.add_column('products', sa.Column('minimal_quantity', sa.Integer(), nullable=True))
        op.execute(sa.text("UPDATE products SET minimal_quantity = 0 WHERE minimal_quantity IS NULL"))


def downgrade() -> None:
    """
    Rimuove le colonne purchase_price e minimal_quantity dalla tabella products.
    """
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    existing_columns = [col['name'] for col in inspector.get_columns('products')]

    if 'purchase_price' in existing_columns:
        op.drop_column('products', 'purchase_price')

    if 'minimal_quantity' in existing_columns:
        op.drop_column('products', 'minimal_quantity')
