"""Vincolo percorsi documenti: corrispettivi (ricevuta+reso) vs fattura/NC."""
from datetime import date, datetime

import pytest

from src.core.container_config import get_configured_container
from src.core.exceptions import BusinessRuleException
from src.schemas.return_schema import ReturnCreateSchema, ReturnItemSchema
from src.schemas.ricevuta_schema import RicevutaCreateSchema
from src.services.interfaces.fiscal_document_service_interface import IFiscalDocumentService
from src.services.interfaces.ricevuta_service_interface import IRicevutaService
from src.services.routers.order_document_service import OrderDocumentService
from tests.helpers.fiscal_test_helpers import (
    seed_company_info,
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
def company_info(db_session):
    seed_company_info(db_session)


@pytest.fixture
def fiscal_service(db_session):
    container = get_configured_container()
    return container.resolve_with_session(IFiscalDocumentService, db_session)


@pytest.fixture
def ricevuta_service(db_session, company_info):
    container = get_configured_container()
    return container.resolve_with_session(IRicevutaService, db_session)


class TestOrderDocumentPathGuards:
    def test_ensure_can_create_invoice_blocked_by_ricevuta(self, db_session, tax):
        order, _ = seed_paid_order(
            db_session, tax, reference="G-RICE", order_date=datetime(2026, 7, 1)
        )
        from src.models.customer import Customer

        customer = (
            db_session.query(Customer)
            .filter(Customer.id_customer == order.id_customer)
            .first()
        )
        seed_ricevuta(
            db_session, order, customer, emission_date=date(2026, 7, 2)
        )

        with pytest.raises(BusinessRuleException, match="ricevuta"):
            OrderDocumentService(db_session).ensure_can_create_invoice(order.id_order)

    def test_ensure_can_create_invoice_blocked_by_return(self, db_session, tax):
        order, detail = seed_paid_order(
            db_session, tax, reference="G-RET", order_date=datetime(2026, 7, 1)
        )
        seed_return(
            db_session,
            tax,
            order,
            detail,
            return_date=datetime(2026, 7, 3),
        )

        with pytest.raises(BusinessRuleException, match="reso"):
            OrderDocumentService(db_session).ensure_can_create_invoice(order.id_order)

    def test_ensure_can_create_corrispettivi_blocked_by_invoice(
        self, db_session, tax
    ):
        order, _ = seed_paid_order(
            db_session, tax, reference="G-INV", order_date=datetime(2026, 7, 1)
        )
        seed_invoice(db_session, order)

        with pytest.raises(BusinessRuleException, match="già fatturato"):
            OrderDocumentService(db_session).ensure_can_create_corrispettivi_document(
                order.id_order
            )


class TestCreateInvoiceBlocked:
    @pytest.mark.asyncio
    async def test_create_invoice_blocked_when_return_exists(
        self, db_session, fiscal_service, tax
    ):
        order, detail = seed_paid_order(
            db_session, tax, reference="INV-BLK-RET", order_date=datetime(2026, 7, 5)
        )
        seed_return(
            db_session,
            tax,
            order,
            detail,
            return_date=datetime(2026, 7, 6),
        )

        with pytest.raises(BusinessRuleException, match="reso"):
            await fiscal_service.create_invoice(order.id_order)


class TestCreateReturnBlocked:
    @pytest.mark.asyncio
    async def test_create_return_blocked_when_invoice_exists(
        self, db_session, fiscal_service, tax
    ):
        order, detail = seed_paid_order(
            db_session, tax, reference="RET-BLK-INV", order_date=datetime(2026, 7, 7)
        )
        seed_invoice(db_session, order)

        with pytest.raises(BusinessRuleException, match="già fatturato"):
            await fiscal_service.create_return(
                order,
                ReturnCreateSchema(
                    order_details=[
                        ReturnItemSchema(
                            id_order_detail=detail.id_order_detail,
                            quantity=1,
                            id_tax=tax.id_tax,
                        )
                    ],
                ),
            )


class TestCreateRicevutaBlocked:
    def test_create_ricevuta_blocked_when_invoice_exists(
        self, db_session, ricevuta_service, tax
    ):
        order, _ = seed_paid_order(
            db_session, tax, reference="RIC-BLK-INV", order_date=datetime(2026, 7, 8)
        )
        seed_invoice(db_session, order)

        with pytest.raises(BusinessRuleException, match="già fatturato"):
            ricevuta_service.create_ricevuta(
                RicevutaCreateSchema(
                    id_order=order.id_order, data_emissione=date(2026, 7, 9)
                )
            )
