#!/usr/bin/env python3
"""
Migration: ricevute.data_emissione DATE → DATETIME.

Conserva i valori esistenti (MySQL li porta a mezzanotte).
Nuove ricevute salvano data e ora (UTC naive, come Order.date_add).

Uso:
    python scripts/migrations/alter_ricevute_data_emissione_datetime.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import inspect, text

from src.database import engine


def upgrade() -> None:
    inspector = inspect(engine)
    if not inspector.has_table("ricevute"):
        print("Tabella ricevute assente, skip.")
        return

    columns = {col["name"]: col for col in inspector.get_columns("ricevute")}
    col_type = str(columns.get("data_emissione", {}).get("type", "")).upper()
    if "DATETIME" in col_type:
        print("Colonna data_emissione già DATETIME, skip.")
        return

    with engine.begin() as conn:
        conn.execute(
            text(
                "ALTER TABLE ricevute "
                "MODIFY COLUMN data_emissione DATETIME NOT NULL"
            )
        )
    print("Colonna ricevute.data_emissione convertita in DATETIME.")


if __name__ == "__main__":
    upgrade()
