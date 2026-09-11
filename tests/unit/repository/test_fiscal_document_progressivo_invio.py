"""ProgressivoInvio unico su fatture e NC (serie SDI condivisa)."""
from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from src.models.address import Address
from src.models.customer import Customer
from src.models.fiscal_document import FiscalDocument
from src.models.fiscal_document_detail import FiscalDocumentDetail
from src.repository.fiscal_document_repository import FiscalDocumentRepository
from tests.helpers.fiscal_test_helpers import seed_country, seed_paid_order, seed_tax


@pytest.fixture
def repo(db_session):
    return FiscalDocumentRepository(db_session)


@pytest.fixture
def tax(db_session):
    return seed_tax(db_session)


def _seed_invoice(db_session, tax, *, document_number="000001", progressivo_invio="000001"):
    country = seed_country(db_session, iso_code="IT", name="Italia")
    customer = Customer(
        id_lang=1,
        firstname="Mario",
        lastname="Rossi",
        email="prog-test@example.com",
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
        reference="PROG-INV",
        order_date=datetime(2026, 8, 21, 10, 0, 0),
        with_shipping=True,
        product_qty=1,
        unit_net=Decimal("100.00"),
        unit_gross=Decimal("122.00"),
        country_iso="IT",
    )
    order.id_address_invoice = address.id_address
    db_session.commit()

    invoice = FiscalDocument(
        document_type="invoice",
        tipo_documento_fe="TD01",
        id_order=order.id_order,
        status="pending",
        is_electronic=True,
        includes_shipping=True,
        document_number=document_number,
        progressivo_invio=progressivo_invio,
        products_total_price_net=Decimal("100.00"),
        products_total_price_with_tax=Decimal("122.00"),
        total_price_net=Decimal("110.00"),
        total_price_with_tax=Decimal("134.20"),
    )
    db_session.add(invoice)
    db_session.commit()
    db_session.refresh(invoice)

    db_session.add(
        FiscalDocumentDetail(
            id_fiscal_document=invoice.id_fiscal_document,
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
    return invoice


class TestProgressivoInvioAssignment:
    def test_credit_note_gets_next_shared_progressivo(self, db_session, repo, tax):
        invoice = _seed_invoice(db_session, tax)
        credit_note = repo.create_credit_note(
            id_invoice=invoice.id_fiscal_document,
            reason="Storno",
            is_partial=False,
            include_shipping=True,
        )
        assert credit_note.document_number == "000001"
        assert invoice.progressivo_invio == "000001"
        assert credit_note.progressivo_invio == "000002"
        assert credit_note.progressivo_invio != credit_note.document_number or (
            invoice.document_number == credit_note.document_number
        )

    def test_create_invoice_assigns_progressivo(self, db_session, repo, tax):
        invoice = _seed_invoice(
            db_session, tax, document_number="000010", progressivo_invio="000010"
        )
        created = repo.create_invoice(invoice.id_order)
        assert created.progressivo_invio == "000011"
        assert created.document_number == "000011"

    def test_assign_next_progressivo_after_scarto(self, db_session, repo, tax):
        invoice = _seed_invoice(db_session, tax, progressivo_invio="000005")
        invoice.sdi_status = "scartata"
        db_session.commit()

        next_value = repo.assign_next_progressivo_invio(invoice)
        db_session.flush()
        assert next_value == "000006"
        assert invoice.progressivo_invio == "000006"

    def test_apply_sdi_resend_xml_clears_sdi_outcome(self, db_session, repo, tax):
        invoice = _seed_invoice(db_session, tax)
        invoice.status = "sent"
        invoice.sdi_status = "scartata"
        invoice.identificativo_sdi = "11111111111"
        invoice.xml_content = "<old/>"
        invoice.filename = "IT02046570426_000001.xml"
        db_session.commit()

        updated = repo.apply_sdi_resend_xml(
            invoice.id_fiscal_document,
            filename="IT02046570426_000002.xml",
            xml_content="<new/>",
        )
        assert updated.status == "generated"
        assert updated.sdi_status is None
        assert updated.identificativo_sdi is None
        assert updated.xml_content == "<new/>"
        assert updated.filename == "IT02046570426_000002.xml"

    def test_duplicate_progressivo_rejected(self, db_session, tax):
        invoice = _seed_invoice(db_session, tax)
        dup = FiscalDocument(
            document_type="credit_note",
            tipo_documento_fe="TD04",
            id_order=invoice.id_order,
            id_fiscal_document_ref=invoice.id_fiscal_document,
            status="pending",
            is_electronic=True,
            document_number="000001",
            progressivo_invio="000001",
        )
        db_session.add(dup)
        with pytest.raises(IntegrityError):
            db_session.commit()
