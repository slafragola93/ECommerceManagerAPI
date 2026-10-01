"""add failed_attempts to mfa_pending_sessions

Revision ID: 20261001_0001
Revises: 20260929_0001
Create Date: 2026-10-01
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261001_0001"
down_revision: Union[str, None] = "20260929_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    tables = inspector.get_table_names()

    if "mfa_pending_sessions" not in tables:
        return

    columns = {col["name"] for col in inspector.get_columns("mfa_pending_sessions")}
    if "failed_attempts" not in columns:
        op.add_column(
            "mfa_pending_sessions",
            sa.Column(
                "failed_attempts",
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
        )


def downgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    tables = inspector.get_table_names()

    if "mfa_pending_sessions" not in tables:
        return

    columns = {col["name"] for col in inspector.get_columns("mfa_pending_sessions")}
    if "failed_attempts" in columns:
        op.drop_column("mfa_pending_sessions", "failed_attempts")
