"""Test export soft XML: ZIP parziale + scarti, 400 solo se zero OK."""
from __future__ import annotations

import io
import json
import zipfile
from datetime import date
from unittest.mock import MagicMock

import pytest

from src.core.exceptions import ValidationException
from src.schemas.fiscal_document_schema import (
    InvoiceExportFiltersSchema,
    InvoiceListExportItemSchema,
)
from src.services.routers.fiscal_document_service import FiscalDocumentService


def _item(doc_id: int) -> InvoiceListExportItemSchema:
    return InvoiceListExportItemSchema(
        id_fiscal_document=doc_id,
        document_type="credit_note",
        document_number=f"{doc_id:05d}",
        status="pending",
        is_electronic=True,
        id_order=1,
        date_add=None,
        total_price_net=10.0,
        total_price_with_tax=12.2,
    )


@pytest.mark.asyncio
class TestExportInvoicesSoftXml:
    async def test_partial_export_returns_zip_with_scarti(self):
        service = FiscalDocumentService(
            MagicMock(), MagicMock(), MagicMock()
        )
        service._list_invoices_for_export = MagicMock(
            return_value=([_item(70), _item(71), _item(72)], 3)
        )

        def prepare(ids):
            return [71], [
                {
                    "id_fiscal_document": 70,
                    "message": "Validazione fallita",
                    "details": {},
                },
                {
                    "id_fiscal_document": 72,
                    "message": "Validazione fallita",
                    "details": {},
                },
            ]

        service._prepare_fiscal_document_ids_for_xml_export = prepare
        service._load_fiscal_document_xml = MagicMock(
            return_value=(b"<xml>ok</xml>", "IT08632861210_00071.xml")
        )

        content, media_type, filename, headers = await service.export_invoices(
            InvoiceExportFiltersSchema(
                document_type="credit_note",
                date_add_from=date(2026, 1, 1),
                date_add_to=date(2026, 12, 31),
            ),
            "xml",
        )

        assert media_type == "application/zip"
        assert headers["X-Export-Partial"] == "true"
        assert headers["X-Export-Success-Count"] == "1"
        assert headers["X-Export-Failed-Count"] == "2"

        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            names = set(archive.namelist())
            assert "IT08632861210_00071.xml" in names
            assert "export-scarti.json" in names
            report = json.loads(archive.read("export-scarti.json").decode("utf-8"))
            assert report["exported_count"] == 1
            assert report["failed_count"] == 2
            assert report["exported_ids"] == [71]

    async def test_all_failed_still_raises_400(self):
        service = FiscalDocumentService(
            MagicMock(), MagicMock(), MagicMock()
        )
        service._list_invoices_for_export = MagicMock(
            return_value=([_item(70)], 1)
        )
        service._prepare_fiscal_document_ids_for_xml_export = MagicMock(
            return_value=(
                [],
                [{"id_fiscal_document": 70, "message": "fail", "details": {}}],
            )
        )

        with pytest.raises(ValidationException, match="Nessun documento esportabile"):
            await service.export_invoices(
                InvoiceExportFiltersSchema(document_type="credit_note"),
                "xml",
            )
