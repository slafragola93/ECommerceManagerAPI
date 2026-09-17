"""remove_platform_fk_allow_zero

Revision ID: b3ba1b4f2909
Revises: 216a478f9b76
Create Date: 2025-11-04 15:23:56.260596

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b3ba1b4f2909'
down_revision: Union[str, None] = '216a478f9b76'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Rimuove il vincolo di foreign key fk_products_platform per permettere
    che id_platform possa essere 0 o qualsiasi valore senza riferimento obbligatorio
    alla tabella platforms.
    """
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    # Verifica se esiste la foreign key fk_products_platform
    fks_products = {fk['name']: fk for fk in inspector.get_foreign_keys('products')}
    
    # Rimuovi la foreign key se esiste
    if 'fk_products_platform' in fks_products:
        op.drop_constraint('fk_products_platform', 'products', type_='foreignkey')
    else:
        # Prova a trovare la FK con altri nomi possibili
        products_platform_fk = None
        for fk_name, fk in fks_products.items():
            if (fk['constrained_columns'] == ['id_platform'] and 
                fk['referred_table'] == 'platforms'):
                products_platform_fk = fk_name
                break
        
        if products_platform_fk:
            op.drop_constraint(products_platform_fk, 'products', type_='foreignkey')


def downgrade() -> None:
    """
    Ripristina il vincolo di foreign key fk_products_platform.
    ATTENZIONE: Questa operazione può fallire se ci sono prodotti con id_platform
    che non corrispondono a valori esistenti nella tabella platforms.
    """
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    # Verifica che non ci siano prodotti con id_platform non validi
    # Prima di ripristinare la foreign key, verifica tutti i valori unici di id_platform
    result = connection.execute(
        sa.text("SELECT DISTINCT id_platform FROM products WHERE id_platform IS NOT NULL")
    )
    platform_ids = [row[0] for row in result.fetchall()]
    
    if platform_ids:
        # Verifica quali id_platform esistono nella tabella platforms
        result = connection.execute(
            sa.text("SELECT id_platform FROM platforms")
        )
        valid_platform_ids = {row[0] for row in result.fetchall()}
        
        # Trova gli id_platform non validi
        invalid_ids = [pid for pid in platform_ids if pid not in valid_platform_ids]
        
        if invalid_ids:
            # Non possiamo ripristinare la FK se ci sono valori non validi
            print(f"Warning: Cannot restore foreign key because products have invalid platform IDs: {invalid_ids}")
            return
    
    # Verifica se la foreign key esiste già
    fks_products = {fk['name']: fk for fk in inspector.get_foreign_keys('products')}
    
    # Crea la foreign key se non esiste
    products_has_fk = any(
        fk['constrained_columns'] == ['id_platform'] and 
        fk['referred_table'] == 'platforms' 
        for fk in fks_products.values()
    )
    
    if not products_has_fk:
        op.create_foreign_key(
            'fk_products_platform', 
            'products', 
            'platforms', 
            ['id_platform'], 
            ['id_platform']
        )
