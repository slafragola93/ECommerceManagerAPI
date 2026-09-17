"""add_id_platform_to_addresses

Revision ID: 11ff33c65e73
Revises: 4b958b35bac0
Create Date: 2025-11-05 09:29:03.893968

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '11ff33c65e73'
down_revision: Union[str, None] = '4b958b35bac0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Aggiunge la colonna id_platform alla tabella addresses.
    - Default: 0 (per indirizzi esistenti e nuovi indirizzi manuali)
    - Nullable: True (permette NULL e 0)
    - Foreign Key: verso platforms.id_platform
    """
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    tables = inspector.get_table_names()
    
    if 'addresses' not in tables:
        print("⚠️  Table addresses not found, skipping migration")
        return
    
    # Verifica se la colonna esiste già
    columns = {col['name']: col for col in inspector.get_columns('addresses')}
    
    if 'id_platform' not in columns:
        # Aggiungi la colonna con default 0
        op.add_column('addresses', sa.Column('id_platform', sa.Integer(), nullable=True, server_default='0'))
        print("✅ Added column id_platform to addresses")
        
        # Imposta il valore di default per gli indirizzi esistenti (se sono NULL)
        op.execute(sa.text("UPDATE addresses SET id_platform = 0 WHERE id_platform IS NULL"))
        print("✅ Set default value 0 for existing addresses")
        
        # Rimuovi server_default dopo aver impostato i valori
        op.alter_column('addresses', 'id_platform', server_default=None)
        
        # Aggiungi Foreign Key verso platforms.id_platform
        try:
            # Verifica che la tabella platforms esista
            if 'platforms' in tables:
                # Trova tutti i valori di id_platform che non esistono in platforms (escludendo NULL)
                invalid_platforms = op.execute(sa.text("""
                    SELECT DISTINCT a.id_platform 
                    FROM addresses a 
                    LEFT JOIN platforms p ON a.id_platform = p.id_platform 
                    WHERE a.id_platform IS NOT NULL AND p.id_platform IS NULL
                """)).fetchall()
                
                # Se ci sono valori non validi, imposta NULL per quegli indirizzi
                if invalid_platforms:
                    invalid_ids = [row[0] for row in invalid_platforms]
                    print(f"⚠️  Found {len(invalid_ids)} invalid platform IDs: {invalid_ids}")
                    # Imposta NULL per tutti gli indirizzi con platform IDs non validi in una singola query
                    placeholders = ','.join(str(invalid_id) for invalid_id in invalid_ids)
                    op.execute(sa.text(f"UPDATE addresses SET id_platform = NULL WHERE id_platform IN ({placeholders})"))
                    print(f"✅ Set NULL for addresses with invalid platform IDs")
                
                # Crea la foreign key (MySQL permette NULL nella foreign key)
                op.create_foreign_key(
                    'fk_addresses_id_platform',
                    'addresses',
                    'platforms',
                    ['id_platform'],
                    ['id_platform']
                )
                print("✅ Created foreign key fk_addresses_id_platform")
            else:
                print("⚠️  Table platforms not found, skipping foreign key creation")
        except Exception as e:
            print(f"⚠️  Could not create foreign key: {e}")
            print("⚠️  Foreign key creation skipped - addresses will have id_platform without FK constraint")
            # Continua anche se la foreign key non può essere creata
    else:
        print("⚠️  Column id_platform already exists in addresses, skipping")


def downgrade() -> None:
    """
    Rimuove la colonna id_platform dalla tabella addresses.
    """
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    tables = inspector.get_table_names()
    
    if 'addresses' not in tables:
        print("⚠️  Table addresses not found, skipping downgrade")
        return
    
    # Verifica se la colonna esiste
    columns = {col['name']: col for col in inspector.get_columns('addresses')}
    
    if 'id_platform' in columns:
        # Rimuovi foreign key se esiste
        foreign_keys = inspector.get_foreign_keys('addresses')
        for fk in foreign_keys:
            if 'id_platform' in fk.get('constrained_columns', []):
                try:
                    op.drop_constraint(fk['name'], 'addresses', type_='foreignkey')
                    print(f"✅ Dropped foreign key {fk['name']}")
                except Exception as e:
                    print(f"⚠️  Could not drop foreign key {fk['name']}: {e}")
        
        # Rimuovi la colonna
        op.drop_column('addresses', 'id_platform')
        print("✅ Dropped column id_platform from addresses")
    else:
        print("⚠️  Column id_platform not found in addresses, skipping downgrade")
