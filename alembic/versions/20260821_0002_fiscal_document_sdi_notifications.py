"""SDI notifications history + sdi_status on fiscal_documents.

Revision ID: 20260821_0002
Revises: 20260821_0001
Create Date: 2026-08-21

NON ESEGUITA in automatico: applicare solo dopo conferma esplicita.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260821_0002"
down_revision: Union[str, None] = "20260821_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    columns = {col["name"] for col in inspector.get_columns("fiscal_documents")}
    if "identificativo_sdi" not in columns:
        op.add_column(
            "fiscal_documents",
            sa.Column("identificativo_sdi", sa.String(length=50), nullable=True),
        )
        op.create_index(
            "ix_fiscal_documents_identificativo_sdi",
            "fiscal_documents",
            ["identificativo_sdi"],
        )
    if "sdi_status" not in columns:
        op.add_column(
            "fiscal_documents",
            sa.Column("sdi_status", sa.String(length=30), nullable=True),
        )
        op.create_index(
            "ix_fiscal_documents_sdi_status",
            "fiscal_documents",
            ["sdi_status"],
        )

    tables = set(inspector.get_table_names())
    if "fiscal_document_sdi_notifications" not in tables:
        op.create_table(
            "fiscal_document_sdi_notifications",
            sa.Column(
                "id_fiscal_document_sdi_notification",
                sa.Integer(),
                primary_key=True,
                autoincrement=True,
            ),
            sa.Column("id_fiscal_document", sa.Integer(), nullable=False),
            sa.Column("notification_type", sa.String(length=4), nullable=False),
            sa.Column("identificativo_sdi", sa.String(length=50), nullable=True),
            sa.Column("nome_file", sa.String(length=255), nullable=True),
            sa.Column("message", sa.String(length=500), nullable=True),
            sa.Column("payload", sa.Text(), nullable=True),
            sa.Column("notified_at", sa.DateTime(), nullable=True),
            sa.Column("date_add", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(
                ["id_fiscal_document"],
                ["fiscal_documents.id_fiscal_document"],
            ),
            sa.UniqueConstraint(
                "id_fiscal_document",
                "notification_type",
                "nome_file",
                name="uq_sdi_notification_doc_type_file",
            ),
        )
        op.create_index(
            "ix_sdi_notifications_id_fiscal_document",
            "fiscal_document_sdi_notifications",
            ["id_fiscal_document"],
        )
        op.create_index(
            "ix_sdi_notifications_type",
            "fiscal_document_sdi_notifications",
            ["notification_type"],
        )
        op.create_index(
            "ix_sdi_notifications_identificativo_sdi",
            "fiscal_document_sdi_notifications",
            ["identificativo_sdi"],
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    if "fiscal_document_sdi_notifications" in tables:
        op.drop_table("fiscal_document_sdi_notifications")

    columns = {col["name"] for col in inspector.get_columns("fiscal_documents")}
    indexes = {idx["name"] for idx in inspector.get_indexes("fiscal_documents")}
    if "ix_fiscal_documents_sdi_status" in indexes:
        op.drop_index("ix_fiscal_documents_sdi_status", table_name="fiscal_documents")
    if "ix_fiscal_documents_identificativo_sdi" in indexes:
        op.drop_index(
            "ix_fiscal_documents_identificativo_sdi", table_name="fiscal_documents"
        )
    if "sdi_status" in columns:
        op.drop_column("fiscal_documents", "sdi_status")
    if "identificativo_sdi" in columns:
        op.drop_column("fiscal_documents", "identificativo_sdi")
