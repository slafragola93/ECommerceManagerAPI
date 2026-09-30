"""create email_templates and email_template_translations

Revision ID: 20260929_0001
Revises: 62e4b40e09f9
Create Date: 2026-09-29
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260929_0001"
down_revision: Union[str, None] = "62e4b40e09f9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    tables = inspector.get_table_names()

    if "email_templates" not in tables:
        op.create_table(
            "email_templates",
            sa.Column("id_email_template", sa.Integer(), nullable=False),
            sa.Column("code", sa.String(80), nullable=False),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("purpose", sa.String(40), nullable=False),
            sa.Column("is_default", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("allowed_variables", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=True, server_default=sa.func.now()),
            sa.PrimaryKeyConstraint("id_email_template"),
            sa.UniqueConstraint("code"),
        )
        op.create_index("ix_email_templates_purpose", "email_templates", ["purpose"])

    if "email_template_translations" not in tables:
        op.create_table(
            "email_template_translations",
            sa.Column("id_email_template_translation", sa.Integer(), nullable=False),
            sa.Column("id_email_template", sa.Integer(), nullable=False),
            sa.Column("locale", sa.String(10), nullable=False),
            sa.Column("subject", sa.String(255), nullable=False),
            sa.Column("body_html", sa.Text(), nullable=False),
            sa.Column("body_text", sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(
                ["id_email_template"],
                ["email_templates.id_email_template"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id_email_template_translation"),
            sa.UniqueConstraint("id_email_template", "locale", name="uq_email_template_locale"),
        )


def downgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    tables = inspector.get_table_names()
    if "email_template_translations" in tables:
        op.drop_table("email_template_translations")
    if "email_templates" in tables:
        op.drop_table("email_templates")
