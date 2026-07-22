"""Test response GET fattura allineata a ricevuta v3."""
from datetime import datetime
from decimal import Decimal

import pytest

from src.core.container_config import get_configured_container
from src.models.fiscal_document import FiscalDocument
from src.models.fiscal_document_detail import FiscalDocumentDetail
from src.models.payment import Payment
from src.services.interfaces.fiscal_document_service_interface import IFiscalDocumentService
from tests.helpers.fiscal_test_helpers import seed_paid_order, seed_tax


@pytest.fixture
def tax(db_session):
    return seed_tax(db_session)


@pytest.fixture
def fiscal_service(db_session):
    container = get_configured_container()
    return container.resolve_with_session(IFiscalDocumentService, db_session)


class TestInvoiceResponseSchema:
    @pytest.mark.asyncio
    async def test_get_invoices_by_order_includes_ricevuta_like_fields(
        self, db_session, fiscal_service, tax
    ):
        payment = Payment(name="Bonifico")
        db_session.add(payment)
        db_session.commit()
        db_session.refresh(payment)

        order, detail = seed_paid_order(
            db_session,
            tax,
            reference="INV-001",
            order_date=datetime(2026, 7, 16, 10, 0, 0),
            with_shipping=True,
            country_iso="IT",
        )
        order.id_payment = payment.id_payment
        db_session.commit()

        invoice = FiscalDocument(
            document_type="invoice",
            tipo_documento_fe="TD01",
            id_order=order.id_order,
            status="issued",
            is_electronic=True,
            includes_shipping=True,
            document_number="1",
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

        results = await fiscal_service.get_invoices_by_order_response(order.id_order)
        assert len(results) == 1
        payload = results[0]

        assert payload.id_fiscal_document == invoice.id_fiscal_document
        assert payload.document_type == "invoice"
        assert payload.tipo_documento_fe == "TD01"
        assert payload.order_reference == "INV-001"
        assert payload.is_payed is True
        assert payload.customer is not None
        assert payload.customer.email == f"INV-001@example.com"
        assert payload.payment is not None
        assert payload.payment.name == "Bonifico"
        assert payload.shipping is not None
        assert payload.shipping_total_price_net == 10.0
        assert payload.shipping_total_price_with_tax == 12.2
        assert payload.address_delivery is not None
        assert len(payload.order_details) == 2
        assert payload.order_details[0].product_name == "Prodotto INV-001"
        assert payload.order_details[0].total_price_with_tax == 122.0
        assert payload.order_details[1].is_shipping is True

    @pytest.mark.asyncio
    async def test_get_invoice_by_id_returns_enriched_schema(
        self, db_session, fiscal_service, tax
    ):
        order, detail = seed_paid_order(
            db_session,
            tax,
            reference="INV-002",
            order_date=datetime(2026, 7, 16, 11, 0, 0),
        )
        invoice = FiscalDocument(
            document_type="invoice",
            id_order=order.id_order,
            status="pending",
            is_electronic=True,
            includes_shipping=False,
            total_price_net=order.total_price_net,
            total_price_with_tax=order.total_price_with_tax,
            products_total_price_net=order.products_total_price_net,
            products_total_price_with_tax=order.products_total_price_with_tax,
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
                unit_price_with_tax=Decimal("122.00"),
                total_price_with_tax=Decimal("122.00"),
                total_price_net=Decimal("100.00"),
            )
        )
        db_session.commit()

        payload = await fiscal_service.get_invoice_response_by_id(
            invoice.id_fiscal_document
        )
        assert payload.document_number is None
        assert payload.status == "pending"
        assert payload.order_details[0].id_order_detail == detail.id_order_detail
        assert payload.shipping_total_price_with_tax is None


class TestCreditNoteDetailResponseSchema:
    @pytest.mark.asyncio
    async def test_get_credit_note_returns_same_shape_as_invoice(
        self, db_session, fiscal_service, tax
    ):
        from src.models.address import Address
        from src.models.customer import Customer
        from tests.helpers.fiscal_test_helpers import seed_country

        country = seed_country(db_session, iso_code="IT", name="Italia")
        customer = Customer(
            id_lang=1,
            firstname="Luigi",
            lastname="Verdi",
            email="nc-detail@example.com",
        )
        db_session.add(customer)
        db_session.commit()
        db_session.refresh(customer)

        address = Address(
            id_customer=customer.id_customer,
            id_country=country.id_country,
            address1="Via Test 1",
            city="Roma",
            postcode="00100",
            state="RM",
            vat="12345678901",
            date_add=datetime(2026, 7, 22).date(),
        )
        db_session.add(address)
        db_session.commit()
        db_session.refresh(address)

        order, detail = seed_paid_order(
            db_session,
            tax,
            reference="CN-DETAIL",
            order_date=datetime(2026, 7, 22, 10, 0, 0),
            with_shipping=True,
            country_iso="IT",
        )
        order.id_customer = customer.id_customer
        order.id_address_invoice = address.id_address
        db_session.commit()

        invoice = FiscalDocument(
            document_type="invoice",
            tipo_documento_fe="TD01",
            id_order=order.id_order,
            status="generated",
            is_electronic=True,
            includes_shipping=True,
            document_number="300",
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

        credit_note = FiscalDocument(
            document_type="credit_note",
            tipo_documento_fe="TD04",
            id_order=order.id_order,
            id_fiscal_document_ref=invoice.id_fiscal_document,
            status="pending",
            is_electronic=True,
            is_partial=True,
            includes_shipping=False,
            document_number="1",
            credit_note_reason="Reso parziale",
            total_price_net=Decimal("100.00"),
            total_price_with_tax=Decimal("122.00"),
        )
        db_session.add(credit_note)
        db_session.commit()
        db_session.refresh(credit_note)

        db_session.add(
            FiscalDocumentDetail(
                id_fiscal_document=credit_note.id_fiscal_document,
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

        payload = await fiscal_service.get_fiscal_document_detail_response_by_id(
            credit_note.id_fiscal_document
        )

        assert payload.document_type == "credit_note"
        assert payload.tipo_documento_fe == "TD04"
        assert payload.id_fiscal_document_ref == invoice.id_fiscal_document
        assert payload.credit_note_reason == "Reso parziale"
        assert payload.is_partial is True
        assert payload.customer is not None
        assert payload.customer.email == "nc-detail@example.com"
        assert payload.address_invoice is not None
        assert len(payload.order_details) == 1
        assert payload.order_details[0].product_name == "Prodotto CN-DETAIL"
        assert payload.shipping_total_price_net is None
