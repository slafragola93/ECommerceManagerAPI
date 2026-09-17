"""ensure_platform_id_0_exists

Revision ID: 216a478f9b76
Revises: c1b296f48b0d
Create Date: 2025-11-04 15:19:37.342317

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '216a478f9b76'
down_revision: Union[str, None] = 'c1b296f48b0d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Assicura che esista una piattaforma con id_platform = 0.
    Questa piattaforma è necessaria per permettere ai prodotti di avere id_platform = 0
    rispettando il vincolo di foreign key.
    """
    connection = op.get_bind()
    
    # Verifica se esiste già una piattaforma con id_platform = 0
    result = connection.execute(
        sa.text("SELECT id_platform FROM platforms WHERE id_platform = 0 LIMIT 1")
    )
    platform_0 = result.fetchone()
    
    if not platform_0:
        # Se non esiste, creala
        # MySQL permette di inserire valori espliciti anche con AUTO_INCREMENT
        # Se la colonna è AUTO_INCREMENT e non possiamo inserire 0 direttamente,
        # disabilitiamo temporaneamente l'auto-increment
        try:
            # Prova prima con INSERT normale
            connection.execute(
                sa.text("""
                    INSERT INTO platforms (id_platform, name, is_default) 
                    VALUES (0, 'Internal/App', 0)
                """)
            )
            connection.commit()
        except Exception:
            # Se fallisce, potrebbe essere perché la colonna è AUTO_INCREMENT
            # In questo caso, modifichiamo temporaneamente la tabella
            connection.rollback()
            try:
                # Disabilita temporaneamente AUTO_INCREMENT
                connection.execute(
                    sa.text("ALTER TABLE platforms MODIFY id_platform INT NOT NULL")
                )
                # Ora inserisci il record con id=0
                connection.execute(
                    sa.text("""
                        INSERT INTO platforms (id_platform, name, is_default) 
                        VALUES (0, 'Internal/App', 0)
                    """)
                )
                # Riabilita AUTO_INCREMENT
                connection.execute(
                    sa.text("ALTER TABLE platforms MODIFY id_platform INT NOT NULL AUTO_INCREMENT")
                )
                connection.commit()
            except Exception:
                connection.rollback()
                # Se anche questo fallisce, usa INSERT IGNORE come fallback
                connection.execute(
                    sa.text("""
                        INSERT IGNORE INTO platforms (id_platform, name, is_default) 
                        VALUES (0, 'Internal/App', 0)
                    """)
                )
                connection.commit()


def downgrade() -> None:
    """
    Rimuove la piattaforma con id_platform = 0 se esiste.
    ATTENZIONE: Questa operazione può fallire se ci sono prodotti con id_platform = 0.
    """
    connection = op.get_bind()
    
    # Verifica se ci sono prodotti che usano id_platform = 0
    result = connection.execute(
        sa.text("SELECT COUNT(*) FROM products WHERE id_platform = 0")
    )
    count = result.fetchone()[0]
    
    if count > 0:
        # Non possiamo rimuovere la piattaforma se ci sono prodotti che la usano
        # In questo caso, la migrazione non fa nulla
        print(f"Warning: Cannot remove platform with id_platform=0 because {count} products use it")
        return
    
    # Rimuovi la piattaforma con id_platform = 0
    connection.execute(
        sa.text("DELETE FROM platforms WHERE id_platform = 0")
    )
    connection.commit()
