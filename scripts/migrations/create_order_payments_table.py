#!/usr/bin/env python3
"""
Migration: crea la tabella order_payments.

Uso:
    python scripts/migrations/create_order_payments_table.py
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
    if inspector.has_table("order_payments"):
        print("Tabella order_payments già presente, skip.")
        return
    Base.metadata.tables["order_payments"].create(bind=engine, checkfirst=True)
    print("Tabella order_payments creata.")


def downgrade() -> None:
    inspector = inspect(engine)
    if not inspector.has_table("order_payments"):
        print("Tabella order_payments assente, skip.")
        return
    Base.metadata.tables["order_payments"].drop(bind=engine, checkfirst=True)
    print("Tabella order_payments eliminata.")


if __name__ == "__main__":
    upgrade()
