"""Test bulk send-to-sdi (facade N cicli Upload)."""
from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError

from src.core.container_config import get_configured_container
from src.models.fiscal_document import FiscalDocument
from src.schemas.fiscal_document_schema import BulkSendToSdiRequestSchema
from src.services.interfaces.fiscal_document_service_interface import IFiscalDocumentService
from tests.helpers.fiscal_test_helpers import seed_paid_order, seed_tax

XML_OK = """<?xml version="1.0"?>
<p:FatturaElettronica xmlns:p="http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2">
  <FatturaElettronicaHeader>
    <DatiTrasmissione>
      <CodiceDestinatario>0000000</CodiceDestinatario>
    </DatiTrasmissione>
  </FatturaElettronicaHeader>
</p:FatturaElettronica>
"""

XML_PEC_GATE = """<?xml version="1.0"?>
<p:FatturaElettronica xmlns:p="http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2">
  <FatturaElettronicaHeader>
    <DatiTrasmissione>
      <CodiceDestinatario>XXXXXXX</CodiceDestinatario>
    </DatiTrasmissione>
  </FatturaElettronicaHeader>
</p:FatturaElettronica>
"""


@pytest.fixture
def tax(db_session):
    return seed_tax(db_session)


@pytest.fixture
def fiscal_service(db_session):
    container = get_configured_container()
    return container.resolve_with_session(IFiscalDocumentService, db_session)


def _seed_doc(
    db_session,
    tax,
    *,
    reference: str,
    status: str = "generated",
    xml_content: str | None = XML_OK,
    filename: str | None = "IT12345678901_000001.xml",
    is_electronic: bool = True,
    sdi_status=None,
) -> FiscalDocument:
    order, _ = seed_paid_order(
        db_session, tax, reference=reference, order_date=datetime(2026, 9, 22)
    )
    doc = FiscalDocument(
        document_type="invoice",
        tipo_documento_fe="TD01" if is_electronic else None,
        id_order=order.id_order,
        status=status,
        is_electronic=is_electronic,
        includes_shipping=False,
        document_number="000001",
        filename=filename,
        xml_content=xml_content,
        sdi_status=sdi_status,
        products_total_price_net=Decimal("100.00"),
        products_total_price_with_tax=Decimal("122.00"),
        total_price_net=Decimal("100.00"),
        total_price_with_tax=Decimal("122.00"),
    )
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)
    return doc


@pytest.mark.asyncio
async def test_bulk_send_success_and_xml_missing(db_session, fiscal_service, tax):
    ok = _seed_doc(db_session, tax, reference="SDI-OK")
    missing = _seed_doc(
        db_session,
        tax,
        reference="SDI-NOXML",
        status="pending",
        xml_content=None,
        filename=None,
    )

    with patch(
        "src.services.external.fatturapa_service.FatturaPAService.upload_fiscal_xml",
        new_callable=AsyncMock,
        return_value={"status": "success"},
    ) as mock_upload:
        result = await fiscal_service.bulk_send_to_sdi(
            [ok.id_fiscal_document, missing.id_fiscal_document],
            send_to_sdi=True,
        )

    assert result.summary["total"] == 2
    assert result.summary["successful_count"] == 1
    assert result.summary["failed_count"] == 1
    assert result.successful[0].id_fiscal_document == ok.id_fiscal_document
    assert result.successful[0].status == "sent"
    assert result.failed[0].error_type == "XML_MISSING"
    mock_upload.assert_awaited_once()

    db_session.refresh(ok)
    assert ok.status == "sent"


@pytest.mark.asyncio
async def test_bulk_send_not_found(db_session, fiscal_service):
    result = await fiscal_service.bulk_send_to_sdi([999999], send_to_sdi=True)
    assert result.failed[0].error_type == "NOT_FOUND"


@pytest.mark.asyncio
async def test_bulk_send_blocked_pending(db_session, fiscal_service, tax):
    doc = _seed_doc(
        db_session,
        tax,
        reference="SDI-PEND",
        status="pending",
        xml_content=XML_OK,
        filename="IT123_1.xml",
    )
    # pending with XML still blocked by send_to_sdi_block_reason
    result = await fiscal_service.bulk_send_to_sdi(
        [doc.id_fiscal_document], send_to_sdi=True
    )
    assert result.failed[0].error_type == "BLOCKED"


@pytest.mark.asyncio
async def test_bulk_send_not_electronic(db_session, fiscal_service, tax):
    doc = _seed_doc(
        db_session,
        tax,
        reference="SDI-PAPER",
        is_electronic=False,
        status="generated",
    )
    result = await fiscal_service.bulk_send_to_sdi(
        [doc.id_fiscal_document], send_to_sdi=True
    )
    assert result.failed[0].error_type == "NOT_ELECTRONIC"


@pytest.mark.asyncio
async def test_bulk_send_pec_gate(db_session, fiscal_service, tax):
    doc = _seed_doc(
        db_session,
        tax,
        reference="SDI-PEC",
        xml_content=XML_PEC_GATE,
    )
    result = await fiscal_service.bulk_send_to_sdi(
        [doc.id_fiscal_document], send_to_sdi=True
    )
    assert result.failed[0].error_type == "PEC_GATE"


@pytest.mark.asyncio
async def test_bulk_send_upload_error(db_session, fiscal_service, tax):
    doc = _seed_doc(db_session, tax, reference="SDI-UPERR")

    with patch(
        "src.services.external.fatturapa_service.FatturaPAService.upload_fiscal_xml",
        new_callable=AsyncMock,
        return_value={"status": "error", "message": "blob failed"},
    ):
        result = await fiscal_service.bulk_send_to_sdi(
            [doc.id_fiscal_document], send_to_sdi=True
        )

    assert result.failed[0].error_type == "UPLOAD_ERROR"
    assert "blob failed" in result.failed[0].error_message
    db_session.refresh(doc)
    assert doc.status == "error"


@pytest.mark.asyncio
async def test_bulk_send_deduplicates(db_session, fiscal_service, tax):
    doc = _seed_doc(db_session, tax, reference="SDI-DUP")

    with patch(
        "src.services.external.fatturapa_service.FatturaPAService.upload_fiscal_xml",
        new_callable=AsyncMock,
        return_value={"status": "success"},
    ) as mock_upload:
        result = await fiscal_service.bulk_send_to_sdi(
            [doc.id_fiscal_document, doc.id_fiscal_document],
            send_to_sdi=True,
        )

    assert result.summary["total"] == 1
    assert result.summary["successful_count"] == 1
    mock_upload.assert_awaited_once()


@pytest.mark.asyncio
async def test_bulk_send_upload_only(db_session, fiscal_service, tax):
    doc = _seed_doc(db_session, tax, reference="SDI-UPONLY")

    with patch(
        "src.services.external.fatturapa_service.FatturaPAService.upload_fiscal_xml",
        new_callable=AsyncMock,
        return_value={"status": "success"},
    ) as mock_upload:
        result = await fiscal_service.bulk_send_to_sdi(
            [doc.id_fiscal_document], send_to_sdi=False
        )

    mock_upload.assert_awaited_once()
    assert mock_upload.await_args.kwargs.get("send_to_sdi") is False
    assert result.successful[0].status == "uploaded"


def test_bulk_send_request_schema_max_25():
    with pytest.raises(ValidationError):
        BulkSendToSdiRequestSchema(ids=list(range(1, 27)))


def test_bulk_send_request_schema_accepts_25():
    schema = BulkSendToSdiRequestSchema(ids=list(range(1, 26)))
    assert len(schema.ids) == 25
    assert schema.send_to_sdi is True
