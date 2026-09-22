"""Test creazione massiva fatture da lista ordini."""
from datetime import date, datetime

import pytest
from pydantic import ValidationError

from src.core.container_config import get_configured_container
from src.models.address import Address
from src.models.customer import Customer
from src.schemas.fiscal_document_schema import BulkInvoiceCreateRequestSchema
from src.services.interfaces.fiscal_document_service_interface import IFiscalDocumentService
from tests.helpers.fiscal_test_helpers import (
    seed_country,
    seed_invoice,
    seed_paid_order,
    seed_return,
    seed_ricevuta,
    seed_tax,
)


@pytest.fixture
def tax(db_session):
    return seed_tax(db_session)


@pytest.fixture
def fiscal_service(db_session):
    container = get_configured_container()
    return container.resolve_with_session(IFiscalDocumentService, db_session)


def _attach_invoice_address(db_session, order, *, email_suffix: str = "inv"):
    """Imposta id_address_invoice richiesto da create_invoice."""
    from src.models.country import Country

    country = (
        db_session.query(Country).filter(Country.iso_code == "IT").first()
    )
    if not country:
        country = seed_country(db_session, iso_code="IT", name="Italia")
    customer = (
        db_session.query(Customer)
        .filter(Customer.id_customer == order.id_customer)
        .first()
    )
    address = Address(
        id_customer=customer.id_customer,
        id_country=country.id_country,
        address1="Via Fattura 1",
        city="Milano",
        postcode="20100",
        state="MI",
        vat="12345678901",
        date_add=datetime(2026, 9, 22).date(),
    )
    db_session.add(address)
    db_session.commit()
    db_session.refresh(address)
    order.id_address_invoice = address.id_address
    db_session.commit()
    return address


@pytest.mark.asyncio
async def test_bulk_create_success_and_already_invoiced(
    db_session, fiscal_service, tax
):
    ok_order, _ = seed_paid_order(
        db_session, tax, reference="BULK-OK", order_date=datetime(2026, 9, 1)
    )
    _attach_invoice_address(db_session, ok_order)

    already, _ = seed_paid_order(
        db_session, tax, reference="BULK-ALR", order_date=datetime(2026, 9, 2)
    )
    _attach_invoice_address(db_session, already)
    seed_invoice(db_session, already)

    result = await fiscal_service.bulk_create_invoices(
        [ok_order.id_order, already.id_order]
    )

    assert result.summary["total"] == 2
    assert result.summary["successful_count"] == 1
    assert result.summary["failed_count"] == 1
    assert len(result.successful) == 1
    assert result.successful[0].order_id == ok_order.id_order
    assert result.successful[0].id_fiscal_document > 0
    assert result.successful[0].status == "pending"
    assert result.failed[0].order_id == already.id_order
    assert result.failed[0].error_type == "ALREADY_INVOICED"


@pytest.mark.asyncio
async def test_bulk_create_not_found(db_session, fiscal_service):
    result = await fiscal_service.bulk_create_invoices([999999])

    assert result.summary["total"] == 1
    assert result.summary["successful_count"] == 0
    assert result.failed[0].error_type == "NOT_FOUND"
    assert result.failed[0].order_id == 999999


@pytest.mark.asyncio
async def test_bulk_create_blocked_by_ricevuta(db_session, fiscal_service, tax):
    order, _ = seed_paid_order(
        db_session, tax, reference="BULK-RICE", order_date=datetime(2026, 9, 3)
    )
    _attach_invoice_address(db_session, order)
    customer = (
        db_session.query(Customer)
        .filter(Customer.id_customer == order.id_customer)
        .first()
    )
    seed_ricevuta(db_session, order, customer, emission_date=date(2026, 9, 4))

    result = await fiscal_service.bulk_create_invoices([order.id_order])

    assert result.summary["successful_count"] == 0
    assert result.failed[0].error_type == "BUSINESS_RULE_ERROR"
    assert "ricevuta" in result.failed[0].error_message.lower()


@pytest.mark.asyncio
async def test_bulk_create_blocked_by_return(db_session, fiscal_service, tax):
    order, detail = seed_paid_order(
        db_session, tax, reference="BULK-RET", order_date=datetime(2026, 9, 5)
    )
    _attach_invoice_address(db_session, order)
    seed_return(
        db_session,
        tax,
        order,
        detail,
        return_date=datetime(2026, 9, 6),
    )

    result = await fiscal_service.bulk_create_invoices([order.id_order])

    assert result.summary["successful_count"] == 0
    assert result.failed[0].error_type == "BUSINESS_RULE_ERROR"
    assert "reso" in result.failed[0].error_message.lower()


@pytest.mark.asyncio
async def test_bulk_create_deduplicates_order_ids(db_session, fiscal_service, tax):
    order, _ = seed_paid_order(
        db_session, tax, reference="BULK-DUP", order_date=datetime(2026, 9, 7)
    )
    _attach_invoice_address(db_session, order)

    result = await fiscal_service.bulk_create_invoices(
        [order.id_order, order.id_order, order.id_order]
    )

    assert result.summary["total"] == 1
    assert result.summary["successful_count"] == 1
    assert len(result.successful) == 1


@pytest.mark.asyncio
async def test_bulk_create_validation_missing_invoice_address(
    db_session, fiscal_service, tax
):
    order, _ = seed_paid_order(
        db_session, tax, reference="BULK-NOADDR", order_date=datetime(2026, 9, 8)
    )
    # nessun id_address_invoice

    result = await fiscal_service.bulk_create_invoices([order.id_order])

    assert result.summary["successful_count"] == 0
    assert result.failed[0].error_type == "VALIDATION_ERROR"


def test_bulk_request_schema_max_100():
    with pytest.raises(ValidationError):
        BulkInvoiceCreateRequestSchema(order_ids=list(range(1, 102)))


def test_bulk_request_schema_rejects_non_positive():
    with pytest.raises(ValidationError):
        BulkInvoiceCreateRequestSchema(order_ids=[1, 0, 3])


def test_bulk_request_schema_accepts_100():
    schema = BulkInvoiceCreateRequestSchema(order_ids=list(range(1, 101)))
    assert len(schema.order_ids) == 100
