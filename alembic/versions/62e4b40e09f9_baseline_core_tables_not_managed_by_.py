"""baseline core tables not managed by migrations

Contesto: il progetto ha usato Base.metadata.create_all() (in src/main.py,
on_event startup) come unico meccanismo di creazione schema fin dall'inizio.
Alembic e' stato introdotto solo in seguito, per tracciare le modifiche
incrementali: la maggior parte delle tabelle core (orders, order_details,
products, customers, addresses, stores, taxes, shipments, fiscal_documents,
fiscal_document_details, payments, ecc.) non e' mai stata creata da nessuna
migration precedente, solo da create_all.

Questa migration NON sostituisce create_all su un DB gia' popolato: per ogni
tabella dei modelli, crea la tabella solo se manca davvero nel DB target
(stesso pattern difensivo gia' usato in 5c44d2400e1d_consolidated_initial_migration).
Su un DB dove le tabelle esistono gia' e' un no-op: nessun DDL viene eseguito.
Su un DB vuoto, crea l'intero schema core corrente, permettendo di rimuovere
create_all senza rompere un bootstrap da zero.

Revision ID: 62e4b40e09f9
Revises: 20260821_0002
Create Date: 2026-09-16 12:12:27.099174

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

import src.models  # noqa: F401 - registra tutti i modelli su Base.metadata
from src.database import Base


# revision identifiers, used by Alembic.
revision: str = '62e4b40e09f9'
down_revision: Union[str, None] = '20260821_0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    missing_tables = [
        table for name, table in Base.metadata.tables.items()
        if name not in existing_tables
    ]

    if missing_tables:
        Base.metadata.create_all(bind=conn, tables=missing_tables)


def downgrade() -> None:
    # Nessun downgrade automatico: le tabelle create da questa baseline
    # non vengono droppate per evitare perdita dati accidentale su DB che
    # le usano gia' in produzione da prima dell'introduzione di questa
    # migration.
    pass
