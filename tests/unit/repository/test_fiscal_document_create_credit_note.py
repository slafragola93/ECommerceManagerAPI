"""Test creazione nota di credito (regressione Decimal + float con spedizione)."""
from datetime import datetime
from decimal import Decimal

import pytest

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


def _seed_electronic_invoice(db_session, tax):
    country = seed_country(db_session, iso_code="IT", name="Italia")
    customer = Customer(
        id_lang=1,
        firstname="Mario",
        lastname="Rossi",
        email="nc-test@example.com",
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
        date_add=datetime(2026, 7, 22).date(),
    )
    db_session.add(address)
    db_session.commit()
    db_session.refresh(address)

    order, detail = seed_paid_order(
        db_session,
        tax,
        reference="NC-CREATE",
        order_date=datetime(2026, 7, 22, 10, 0, 0),
        with_shipping=True,
        product_qty=2,
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
        status="generated",
        is_electronic=True,
        includes_shipping=True,
        document_number="200",
        products_total_price_net=Decimal("200.00"),
        products_total_price_with_tax=Decimal("244.00"),
        total_price_net=Decimal("210.00"),
        total_price_with_tax=Decimal("256.20"),
    )
    db_session.add(invoice)
    db_session.commit()
    db_session.refresh(invoice)

    db_session.add(
        FiscalDocumentDetail(
            id_fiscal_document=invoice.id_fiscal_document,
            id_order_detail=detail.id_order_detail,
            product_qty=2,
            id_tax=tax.id_tax,
            unit_price_net=Decimal("100.00"),
            unit_price_with_tax=Decimal("122.00"),
            total_price_net=Decimal("200.00"),
            total_price_with_tax=Decimal("244.00"),
        )
    )
    db_session.commit()
    return invoice, detail


class TestCreateCreditNote:
    def test_total_credit_note_with_shipping_does_not_raise_decimal_error(
        self, db_session, repo, tax
    ):
        invoice, _detail = _seed_electronic_invoice(db_session, tax)

        credit_note = repo.create_credit_note(
            id_invoice=invoice.id_fiscal_document,
            reason="Reso completo",
            is_partial=False,
            include_shipping=True,
        )

        assert credit_note.document_type == "credit_note"
        assert credit_note.includes_shipping is True
        assert float(credit_note.total_price_with_tax or 0) > 0

    def test_partial_credit_note_with_shipping(self, db_session, repo, tax):
        invoice, detail = _seed_electronic_invoice(db_session, tax)

        credit_note = repo.create_credit_note(
            id_invoice=invoice.id_fiscal_document,
            reason="Reso parziale + spedizione",
            is_partial=True,
            include_shipping=True,
            items=[{"id_order_detail": detail.id_order_detail, "quantity": 1.0}],
        )

        assert credit_note.is_partial is True
        assert credit_note.includes_shipping is True
        assert len(credit_note.details) == 1
