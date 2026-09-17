"""cleanup BE-VIES-1 EU VAT seed from taxes

Revision ID: 20260527_0001
Revises:
Create Date: 2026-05-27

Rimuove le aliquote create dal seed BE-VIES-1 (nota 'BE-VIES-1 seed'),
saltando quelle ancora referenziate da order_details / fiscal_document_details / shippings.

Rollback (downgrade): ripristina il seed chiamando setup_eu_country_taxes (idempotente).
Per ambienti prod preferire: alembic downgrade -1 SOLO in emergenza, poi verificare /init.
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy.orm import Session

from src.database import SessionLocal
from src.vies.eu_vat_seed import (
    SEED_NOTE_MARKER,
    delete_be_vies_1_seed_taxes,
    setup_eu_country_taxes,
)

# revision identifiers, used by Alembic.
revision: str = "20260527_0001"
down_revision: Union[str, None] = "0a615ed0ec5f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()
    deleted = delete_be_vies_1_seed_taxes(connection)
    print(
        f"BE-VIES-CLEANUP-SEED: deleted {deleted} tax row(s) "
        f"(marker: {SEED_NOTE_MARKER})"
    )


def downgrade() -> None:
    """Ripristina seed UE (idempotente). Usare solo per rollback controllato / CI."""
    db: Session = SessionLocal()
    try:
        setup_eu_country_taxes(db)
    finally:
        db.close()
