from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest

from src.models.address import Address
from src.models.customer import Customer
from src.models.fiscal_document import FiscalDocument
from src.models.fiscal_document_detail import FiscalDocumentDetail
from src.repository.fiscal_document_sdi_notification_repository import (
    FiscalDocumentSdiNotificationRepository,
)
from src.services.sync.fatturapa_sdi_events_sync_service import (
    FatturaPASdiEventsSyncService,
)
from tests.helpers.fiscal_test_helpers import seed_country, seed_paid_order, seed_tax

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures" / "fatturapa_sdi"


@pytest.fixture
def tax(db_session):
    return seed_tax(db_session)


def _seed_doc(db_session, tax, progressivo="000001"):
    country = seed_country(db_session, iso_code="IT", name="Italia")
    customer = Customer(
        id_lang=1, firstname="Mario", lastname="Rossi", email="sdi@example.com"
    )
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)
    address = Address(
        id_customer=customer.id_customer,
        id_country=country.id_country,
        address1="Via Roma 1",
        city="Milano",
        postcode="20100",
        state="MI",
        vat="12345678901",
        date_add=datetime(2026, 8, 21).date(),
    )
    db_session.add(address)
    db_session.commit()
    db_session.refresh(address)
    order, detail = seed_paid_order(
        db_session,
        tax,
        reference="SDI-EVT",
        order_date=datetime(2026, 8, 21, 10, 0, 0),
        with_shipping=False,
        product_qty=1,
        unit_net=Decimal("100.00"),
        unit_gross=Decimal("122.00"),
        country_iso="IT",
    )
    order.id_address_invoice = address.id_address
    db_session.commit()
    doc = FiscalDocument(
        document_type="invoice",
        tipo_documento_fe="TD01",
        id_order=order.id_order,
        status="sent",
        is_electronic=True,
        document_number="000001",
        progressivo_invio=progressivo,
    )
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)
    db_session.add(
        FiscalDocumentDetail(
            id_fiscal_document=doc.id_fiscal_document,
            id_order_detail=detail.id_order_detail,
            product_qty=1,
            id_tax=tax.id_tax,
            unit_price_net=Decimal("100.00"),
            unit_price_with_tax=Decimal("122.00"),
            total_price_net=Decimal("100.00"),
            total_price_with_tax=Decimal("122.00"),
        )
    )
    db_session.commit()
    return doc


def _service(db_session):
    svc = FatturaPASdiEventsSyncService.__new__(FatturaPASdiEventsSyncService)
    svc.db = db_session
    svc.repo = FiscalDocumentSdiNotificationRepository(db_session)
    return svc


class TestPersistSdiNotification:
    def test_rc_persists_and_sets_status(self, db_session, tax):
        doc = _seed_doc(db_session, tax, "000001")
        xml = (FIXTURES / "rc_sample.xml").read_text(encoding="utf-8")
        assert _service(db_session).persist_notification(xml_content=xml, nome_file=None) == (
            "saved"
        )
        db_session.refresh(doc)
        assert doc.sdi_status == "consegnata"
        assert doc.identificativo_sdi == "1111111111"
        assert doc.status == "sent"
        rows = FiscalDocumentSdiNotificationRepository(db_session).list_by_document(
            doc.id_fiscal_document
        )
        assert len(rows) == 1
        assert rows[0].notification_type == "RC"

    def test_idempotent_same_notification(self, db_session, tax):
        _seed_doc(db_session, tax, "000002")
        xml = (FIXTURES / "ns_sample.xml").read_text(encoding="utf-8")
        svc = _service(db_session)
        assert svc.persist_notification(xml_content=xml, nome_file=None) == "saved"
        assert svc.persist_notification(xml_content=xml, nome_file=None) == "skipped"

    def test_unknown_progressivo_skipped(self, db_session, tax):
        _seed_doc(db_session, tax, "000099")
        xml = (FIXTURES / "rc_sample.xml").read_text(encoding="utf-8")
        assert _service(db_session).persist_notification(xml_content=xml, nome_file=None) == (
            "skipped"
        )
