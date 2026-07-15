#!/usr/bin/env python3
"""
Migration: aggiunge orders.payment_due_date (DATE, nullable).

Uso:
    python scripts/migrations/add_orders_payment_due_date.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import inspect, text

from src.database import engine


def upgrade() -> None:
    inspector = inspect(engine)
    if not inspector.has_table("orders"):
        print("Tabella orders assente, skip.")
        return

    columns = {col["name"] for col in inspector.get_columns("orders")}
    if "payment_due_date" in columns:
        print("Colonna payment_due_date già presente, skip.")
        return

    with engine.begin() as conn:
        conn.execute(
            text("ALTER TABLE orders ADD COLUMN payment_due_date DATE NULL")
        )
    print("Colonna orders.payment_due_date aggiunta.")


if __name__ == "__main__":
    upgrade()
