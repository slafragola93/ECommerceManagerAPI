"""add_id_carrier_to_orders

Revision ID: 2f5fefbe9555
Revises: 11ff33c65e73
Create Date: 2025-11-05 10:20:56.737934

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2f5fefbe9555'
down_revision: Union[str, None] = '11ff33c65e73'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    tables = inspector.get_table_names()
    
    if 'orders' not in tables:
        print("⚠️  Table orders not found, skipping migration")
        return
    
    columns = {col['name']: col for col in inspector.get_columns('orders')}
    
    if 'id_carrier' not in columns:
        # Add column with default 0
        op.add_column('orders', sa.Column('id_carrier', sa.Integer(), nullable=True, server_default='0'))
        print("✅ Added column id_carrier to orders")
        
        # Set default value 0 for existing orders
        op.execute(sa.text("UPDATE orders SET id_carrier = 0 WHERE id_carrier IS NULL"))
        print("✅ Set default value 0 for existing orders")
        
        # Remove server_default after setting values
        op.alter_column('orders', 'id_carrier', server_default=None)
        
        # Add Foreign Key constraint
        try:
            if 'carriers' in tables:
                # Find all id_carrier values in orders that don't exist in carriers (excluding NULL)
                invalid_carriers = op.execute(sa.text("""
                    SELECT DISTINCT o.id_carrier 
                    FROM orders o 
                    LEFT JOIN carriers c ON o.id_carrier = c.id_carrier 
                    WHERE o.id_carrier IS NOT NULL AND c.id_carrier IS NULL
                """)).fetchall()
                
                # If there are invalid carrier IDs, set them to NULL (or 0 if carrier 0 exists)
                if invalid_carriers:
                    invalid_ids = [row[0] for row in invalid_carriers]
                    print(f"⚠️  Found {len(invalid_ids)} invalid carrier IDs: {invalid_ids}")
                    
                    # Check if carrier with id_carrier=0 exists
                    carrier_zero_exists = op.execute(sa.text("SELECT COUNT(*) FROM carriers WHERE id_carrier = 0")).scalar()
                    
                    if carrier_zero_exists > 0:
                        # Set invalid carriers to 0
                        placeholders = ','.join(str(cid) for cid in invalid_ids)
                        op.execute(sa.text(f"UPDATE orders SET id_carrier = 0 WHERE id_carrier IN ({placeholders})"))
                        print(f"✅ Set invalid carrier IDs to 0")
                    else:
                        # Set invalid carriers to NULL
                        placeholders = ','.join(str(cid) for cid in invalid_ids)
                        op.execute(sa.text(f"UPDATE orders SET id_carrier = NULL WHERE id_carrier IN ({placeholders})"))
                        print(f"✅ Set invalid carrier IDs to NULL")
                
                # Create the foreign key (MySQL allows NULL in foreign keys)
                op.create_foreign_key(
                    'fk_orders_id_carrier',
                    'orders',
                    'carriers',
                    ['id_carrier'],
                    ['id_carrier']
                )
                print("✅ Created foreign key fk_orders_id_carrier")
            else:
                print("⚠️  Table carriers not found, skipping foreign key creation")
        except Exception as e:
            print(f"⚠️  Could not create foreign key: {e}")
            print("⚠️  Foreign key creation skipped - orders will have id_carrier without FK constraint")
    else:
        print("⚠️  Column id_carrier already exists in orders, skipping")


def downgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    tables = inspector.get_table_names()
    
    if 'orders' not in tables:
        print("⚠️  Table orders not found, skipping downgrade")
        return
    
    columns = {col['name']: col for col in inspector.get_columns('orders')}
    
    if 'id_carrier' in columns:
        # Drop foreign key if it exists
        try:
            foreign_keys = inspector.get_foreign_keys('orders')
            for fk in foreign_keys:
                if 'id_carrier' in fk.get('constrained_columns', []):
                    fk_name = fk['name']
                    try:
                        op.drop_constraint(fk_name, 'orders', type_='foreignkey')
                        print(f"✅ Dropped foreign key {fk_name} from orders")
                    except Exception as e:
                        print(f"⚠️  Could not drop foreign key {fk_name}: {e}")
            
            # Try to drop the common foreign key name
            try:
                op.drop_constraint('fk_orders_id_carrier', 'orders', type_='foreignkey')
                print("✅ Dropped foreign key fk_orders_id_carrier")
            except Exception:
                pass
        except Exception as e:
            print(f"⚠️  Error checking foreign keys: {e}")
        
        # Drop column
        op.drop_column('orders', 'id_carrier')
        print("✅ Dropped column id_carrier from orders")
    else:
        print("⚠️  Column id_carrier not found in orders, skipping downgrade")
