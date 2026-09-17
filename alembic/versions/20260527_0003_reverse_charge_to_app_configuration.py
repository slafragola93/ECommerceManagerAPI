"""Sposta reverse_charge_id_tax da settings a app_configurations

Revision ID: 20260527_0003
Revises: 20260527_0002
Create Date: 2026-05-27
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260527_0003"
down_revision: Union[str, None] = "20260527_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

VIES_CATEGORY = "vies"
REVERSE_CHARGE_NAME = "reverse_charge_id_tax"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    if "settings" in tables:
        row = bind.execute(
            sa.text(
                "SELECT reverse_charge_id_tax FROM settings WHERE id_settings = 1"
            )
        ).fetchone()
        id_tax = row[0] if row and row[0] is not None else None

        if id_tax is not None and "app_configurations" in tables:
            existing = bind.execute(
                sa.text(
                    """
                    SELECT id_app_configuration FROM app_configurations
                    WHERE LOWER(category) = :cat AND LOWER(name) = :name
                    LIMIT 1
                    """
                ),
                {"cat": VIES_CATEGORY, "name": REVERSE_CHARGE_NAME},
            ).fetchone()

            if existing:
                bind.execute(
                    sa.text(
                        """
                        UPDATE app_configurations
                        SET value = :val
                        WHERE id_app_configuration = :id
                        """
                    ),
                    {"val": str(id_tax), "id": existing[0]},
                )
            else:
                bind.execute(
                    sa.text(
                        """
                        INSERT INTO app_configurations
                            (id_lang, category, name, value, description, is_encrypted)
                        VALUES
                            (0, :cat, :name, :val, :desc, 0)
                        """
                    ),
                    {
                        "cat": VIES_CATEGORY,
                        "name": REVERSE_CHARGE_NAME,
                        "val": str(id_tax),
                        "desc": "ID Tax aliquota 0% reverse charge VIES (eligible)",
                    },
                )

        op.drop_constraint(
            "fk_settings_reverse_charge_tax", "settings", type_="foreignkey"
        )
        op.drop_index("ix_settings_reverse_charge_id_tax", table_name="settings")
        op.drop_table("settings")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    if "settings" not in tables:
        op.create_table(
            "settings",
            sa.Column("id_settings", sa.Integer(), primary_key=True),
            sa.Column("reverse_charge_id_tax", sa.Integer(), nullable=True),
        )
        op.create_foreign_key(
            "fk_settings_reverse_charge_tax",
            "settings",
            "taxes",
            ["reverse_charge_id_tax"],
            ["id_tax"],
            ondelete="SET NULL",
        )
        op.create_index(
            "ix_settings_reverse_charge_id_tax",
            "settings",
            ["reverse_charge_id_tax"],
        )

    id_tax = None
    if "app_configurations" in tables:
        row = bind.execute(
            sa.text(
                """
                SELECT value FROM app_configurations
                WHERE LOWER(category) = :cat AND LOWER(name) = :name
                LIMIT 1
                """
            ),
            {"cat": VIES_CATEGORY, "name": REVERSE_CHARGE_NAME},
        ).fetchone()
        if row and row[0]:
            try:
                id_tax = int(str(row[0]).strip())
            except ValueError:
                id_tax = None

    bind.execute(
        sa.text(
            "INSERT INTO settings (id_settings, reverse_charge_id_tax) "
            "VALUES (1, :id_tax) ON DUPLICATE KEY UPDATE reverse_charge_id_tax = :id_tax"
        ),
        {"id_tax": id_tax},
    )
