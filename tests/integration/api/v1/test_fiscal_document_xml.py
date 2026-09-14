"""Integration API — download XML on-demand e assenza xml_content nel JSON."""
from datetime import datetime

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from src.models.fiscal_document import FiscalDocument
from src.services.routers.auth_service import get_current_user
from tests.helpers.fiscal_test_helpers import (
    admin_full_crud_user,
    seed_paid_order,
    seed_tax,
)

SAMPLE_XML = (
    '<?xml version="1.0"?>'
    '<p:FatturaElettronica xmlns:p="http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2">'
    "<DatiTrasmissione><IdTrasmittente>"
    "<IdPaese>IT</IdPaese><IdCodice>01558670780</IdCodice>"
    "</IdTrasmittente><ProgressivoInvio>XYZ99</ProgressivoInvio>"
    "</DatiTrasmissione></p:FatturaElettronica>"
)


@pytest.fixture
def fiscal_admin_client(test_app) -> TestClient:
    test_app.dependency_overrides[get_current_user] = admin_full_crud_user
    return TestClient(test_app)


@pytest.fixture
def tax(db_session):
    return seed_tax(db_session)


def _seed_invoice_with_xml(db_session, tax) -> FiscalDocument:
    order, _ = seed_paid_order(
        db_session,
        tax,
        reference="API-XML",
        order_date=datetime(2026, 9, 14, 9, 0, 0),
    )
    invoice = FiscalDocument(
        document_type="invoice",
        tipo_documento_fe="TD01",
        id_order=order.id_order,
        status="generated",
        is_electronic=True,
        includes_shipping=False,
        xml_content=SAMPLE_XML,
        filename="legacy.xml",
    )
    db_session.add(invoice)
    db_session.commit()
    db_session.refresh(invoice)
    return invoice


@pytest.mark.integration
class TestFiscalDocumentXmlAPI:
    def test_download_xml_attachment(self, fiscal_admin_client, db_session, tax):
        invoice = _seed_invoice_with_xml(db_session, tax)
        resp = fiscal_admin_client.get(
            f"/api/v1/fiscal_documents/{invoice.id_fiscal_document}/xml"
        )
        assert resp.status_code == status.HTTP_200_OK
        assert "application/xml" in resp.headers["content-type"]
        assert "IT01558670780_XYZ99.xml" in resp.headers["content-disposition"]
        assert resp.content.startswith(b"<?xml")

    def test_download_xml_not_found(self, fiscal_admin_client):
        resp = fiscal_admin_client.get("/api/v1/fiscal_documents/999999/xml")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_download_xml_without_content(self, fiscal_admin_client, db_session, tax):
        order, _ = seed_paid_order(
            db_session,
            tax,
            reference="API-NO-XML",
            order_date=datetime(2026, 9, 14, 9, 30, 0),
        )
        invoice = FiscalDocument(
            document_type="invoice",
            id_order=order.id_order,
            status="pending",
            is_electronic=True,
            includes_shipping=False,
        )
        db_session.add(invoice)
        db_session.commit()
        db_session.refresh(invoice)

        resp = fiscal_admin_client.get(
            f"/api/v1/fiscal_documents/{invoice.id_fiscal_document}/xml"
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_detail_omits_xml_by_default(self, fiscal_admin_client, db_session, tax):
        invoice = _seed_invoice_with_xml(db_session, tax)
        resp = fiscal_admin_client.get(
            f"/api/v1/fiscal_documents/{invoice.id_fiscal_document}"
        )
        assert resp.status_code == status.HTTP_200_OK
        body = resp.json()
        assert "xml_content" not in body

    def test_detail_include_xml_query(self, fiscal_admin_client, db_session, tax):
        invoice = _seed_invoice_with_xml(db_session, tax)
        resp = fiscal_admin_client.get(
            f"/api/v1/fiscal_documents/{invoice.id_fiscal_document}",
            params={"include_xml": True},
        )
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["xml_content"] == SAMPLE_XML

    def test_list_omits_xml_content(self, fiscal_admin_client, db_session, tax):
        invoice = _seed_invoice_with_xml(db_session, tax)
        resp = fiscal_admin_client.get("/api/v1/fiscal_documents/")
        assert resp.status_code == status.HTTP_200_OK
        rows = resp.json()["documents"]
        match = next(
            r for r in rows if r["id_fiscal_document"] == invoice.id_fiscal_document
        )
        assert "xml_content" not in match
        assert SAMPLE_XML not in resp.text
