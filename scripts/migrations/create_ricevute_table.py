#!/usr/bin/env python3
"""
Migration: crea la tabella ricevute.

Uso:
    python scripts/migrations/create_ricevute_table.py

In alternativa, con Alembic (DB MySQL configurato in .env):
    alembic revision --autogenerate -m "create ricevute table"
    alembic upgrade head

Copiare questo file in alembic/versions/ se si usa il workflow Alembic locale.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import inspect

from src.database import Base, engine
import src.models  # noqa: F401


def upgrade() -> None:
    inspector = inspect(engine)
    if inspector.has_table("ricevute"):
        print("Tabella ricevute già presente, skip.")
        return
    Base.metadata.tables["ricevute"].create(bind=engine, checkfirst=True)
    print("Tabella ricevute creata.")


def downgrade() -> None:
    inspector = inspect(engine)
    if not inspector.has_table("ricevute"):
        print("Tabella ricevute assente, skip.")
        return
    Base.metadata.tables["ricevute"].drop(bind=engine, checkfirst=True)
    print("Tabella ricevute eliminata.")


if __name__ == "__main__":
    upgrade()
