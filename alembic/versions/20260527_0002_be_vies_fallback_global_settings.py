"""BE-VIES-FALLBACK-GLOBAL: tabella settings + reverse_charge_id_tax

Revision ID: 20260527_0002
Revises: 20260527_0001
Create Date: 2026-05-27
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260527_0002"
down_revision: Union[str, None] = "20260527_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "settings" not in inspector.get_table_names():
        op.create_table(
            "settings",
            sa.Column("id_settings", sa.Integer(), primary_key=True),
            sa.Column("reverse_charge_id_tax", sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(
                ["reverse_charge_id_tax"],
                ["taxes.id_tax"],
                name="fk_settings_reverse_charge_tax",
                ondelete="SET NULL",
            ),
        )
        op.create_index(
            "ix_settings_reverse_charge_id_tax",
            "settings",
            ["reverse_charge_id_tax"],
        )
        op.execute(
            sa.text(
                "INSERT INTO settings (id_settings, reverse_charge_id_tax) VALUES (1, NULL)"
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "settings" in inspector.get_table_names():
        op.drop_index("ix_settings_reverse_charge_id_tax", table_name="settings")
        op.drop_table("settings")
