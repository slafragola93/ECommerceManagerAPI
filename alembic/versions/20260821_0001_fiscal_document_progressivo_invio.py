"""Add fiscal_documents.progressivo_invio (unique SDI series).

Revision ID: 20260821_0001
Revises: 20260812_0001
Create Date: 2026-08-21

NON ESEGUITA in automatico: applicare solo dopo conferma esplicita.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260821_0001"
down_revision: Union[str, None] = "20260812_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ELECTRONIC_TYPES = ("invoice", "credit_note")
_REASSIGNABLE = ("pending", "generated", "error")


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    columns = {col["name"] for col in inspector.get_columns("fiscal_documents")}
    if "progressivo_invio" not in columns:
        op.add_column(
            "fiscal_documents",
            sa.Column("progressivo_invio", sa.String(length=10), nullable=True),
        )

    fiscal = sa.table(
        "fiscal_documents",
        sa.column("id_fiscal_document", sa.Integer),
        sa.column("document_type", sa.String),
        sa.column("document_number", sa.String),
        sa.column("progressivo_invio", sa.String),
        sa.column("xml_content", sa.Text),
        sa.column("status", sa.String),
        sa.column("is_electronic", sa.Boolean),
    )

    rows = connection.execute(
        sa.select(
            fiscal.c.id_fiscal_document,
            fiscal.c.document_number,
            fiscal.c.progressivo_invio,
            fiscal.c.xml_content,
            fiscal.c.status,
            fiscal.c.document_type,
            fiscal.c.is_electronic,
        ).where(
            fiscal.c.is_electronic.is_(True),
            fiscal.c.document_type.in_(_ELECTRONIC_TYPES),
        )
    ).fetchall()

    used: dict[str, int] = {}
    max_num = 0

    def _parse(raw: object) -> int | None:
        if raw is None:
            return None
        text = str(raw).strip()
        if not text.isdigit():
            return None
        return int(text)

    def _from_xml(xml_content: object) -> str | None:
        if not xml_content:
            return None
        import re

        match = re.search(
            r"<ProgressivoInvio>\s*([^<]+)\s*</ProgressivoInvio>",
            str(xml_content),
        )
        if not match:
            return None
        value = match.group(1).strip()
        return value or None

    updates: list[tuple[int, str]] = []
    deferred: list[tuple] = []

    for row in rows:
        current = (row.progressivo_invio or "").strip() or None
        if not current:
            current = _from_xml(row.xml_content) or (
                (row.document_number or "").strip() or None
            )
        if not current:
            deferred.append(row)
            continue
        parsed = _parse(current)
        if parsed is not None:
            max_num = max(max_num, parsed)
        owner = used.get(current)
        if owner is None:
            used[current] = row.id_fiscal_document
            if row.progressivo_invio != current:
                updates.append((row.id_fiscal_document, current))
        else:
            deferred.append(row)

    for row in deferred:
        if row.status not in _REASSIGNABLE and (row.progressivo_invio or "").strip():
            continue
        max_num += 1
        new_value = str(max_num).zfill(6)
        if len(new_value) > 10:
            raise RuntimeError("ProgressivoInvio overflow oltre 10 caratteri")
        while new_value in used:
            max_num += 1
            new_value = str(max_num).zfill(6)
        used[new_value] = row.id_fiscal_document
        updates.append((row.id_fiscal_document, new_value))

    for doc_id, value in updates:
        connection.execute(
            fiscal.update()
            .where(fiscal.c.id_fiscal_document == doc_id)
            .values(progressivo_invio=value)
        )

    inspector = sa.inspect(connection)
    indexes = {idx["name"] for idx in inspector.get_indexes("fiscal_documents")}
    if "uq_fiscal_documents_progressivo_invio" not in indexes:
        op.create_index(
            "uq_fiscal_documents_progressivo_invio",
            "fiscal_documents",
            ["progressivo_invio"],
            unique=True,
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    indexes = {idx["name"] for idx in inspector.get_indexes("fiscal_documents")}
    if "uq_fiscal_documents_progressivo_invio" in indexes:
        op.drop_index(
            "uq_fiscal_documents_progressivo_invio",
            table_name="fiscal_documents",
        )
    columns = {col["name"] for col in inspector.get_columns("fiscal_documents")}
    if "progressivo_invio" in columns:
        op.drop_column("fiscal_documents", "progressivo_invio")
