#!/usr/bin/env python3
"""
Migration: colonne mail_status / mail_error_message per stati rapidi FE.

Tabelle: fiscal_documents, ricevute, fatture_acquisto_sync

Uso:
    python scripts/migrations/add_document_mail_quick_status.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from sqlalchemy import inspect, text

from src.database import engine

TARGETS = (
    "fiscal_documents",
    "ricevute",
    "fatture_acquisto_sync",
)

COLUMNS = {
    "mail_status": "VARCHAR(20) NULL",
    "mail_error_message": "VARCHAR(255) NULL",
}


def upgrade() -> None:
    inspector = inspect(engine)
    with engine.begin() as conn:
        for table in TARGETS:
            if not inspector.has_table(table):
                print(f"Tabella {table} assente, skip.")
                continue
            existing = {col["name"] for col in inspector.get_columns(table)}
            for name, ddl in COLUMNS.items():
                if name in existing:
                    print(f"{table}.{name} gia' presente, skip.")
                    continue
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
                print(f"{table}.{name} aggiunta.")


if __name__ == "__main__":
    upgrade()
