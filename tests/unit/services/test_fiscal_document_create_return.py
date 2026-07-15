"""Test creazione resi via FiscalDocumentService e impatto corrispettivi."""
from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy import func

from src.core.container_config import get_configured_container
from src.core.exceptions import ValidationException
from src.models.fiscal_document import FiscalDocument
from src.models.order import Order
from src.repository.corrispettivo_repository import CorrispettivoRepository
from src.schemas.return_schema import ReturnCreateSchema, ReturnItemSchema
from src.services.interfaces.fiscal_document_service_interface import IFiscalDocumentService
from tests.helpers.fiscal_test_helpers import seed_invoice, seed_paid_order, seed_tax


@pytest.fixture(autouse=True)
def sqlite_local_day(monkeypatch):
    monkeypatch.setattr(
        CorrispettivoRepository,
        "_local_day_expr",
        lambda self, column: func.date(column),
    )


@pytest.fixture
def tax(db_session):
    return seed_tax(db_session)


@pytest.fixture
def fiscal_service(db_session):
    container = get_configured_container()
    return container.resolve_with_session(IFiscalDocumentService, db_session)


@pytest.fixture
def repo(db_session):
    return CorrispettivoRepository(db_session)


class TestFiscalDocumentCreateReturn:
    @pytest.mark.asyncio
    async def test_create_partial_return(self, db_session, fiscal_service, tax, repo):
        order, detail = seed_paid_order(
            db_session,
            tax,
            reference="RET-PART",
            order_date=datetime(2026, 7, 8, 10, 0, 0),
            product_qty=3,
        )

        return_doc = await fiscal_service.create_return(
            order,
            ReturnCreateSchema(
                order_details=[
                    ReturnItemSchema(
                        id_order_detail=detail.id_order_detail,
                        quantity=1,
                        id_tax=tax.id_tax,
                    )
                ],
                includes_shipping=False,
            ),
        )

        assert return_doc.document_type == "return"
        assert return_doc.status == "issued"

        movements = repo.fetch_movements(2026, 7)
        returns_net = sum(m.returns_amount for m in movements)
        assert returns_net > Decimal("0")

    @pytest.mark.asyncio
    async def test_create_return_with_shipping_in_movements(
        self, db_session, fiscal_service, tax, repo
    ):
        order, detail = seed_paid_order(
            db_session,
            tax,
            reference="RET-SHIP",
            order_date=datetime(2026, 7, 9, 10, 0, 0),
            with_shipping=True,
        )

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
                includes_shipping=True,
            ),
        )

        movements = repo.fetch_movements(2026, 7)
        shipping_returns = [m for m in movements if m.is_shipping and m.returns_amount]
        assert len(shipping_returns) >= 1

    @pytest.mark.asyncio
    async def test_create_return_exceeding_quantity_raises(
        self, db_session, fiscal_service, tax
    ):
        order, detail = seed_paid_order(
            db_session,
            tax,
            reference="RET-OVER",
            order_date=datetime(2026, 7, 11, 10, 0, 0),
            product_qty=1,
        )

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

        with pytest.raises(ValidationException):
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

    @pytest.mark.asyncio
    async def test_return_on_invoiced_order_excluded_from_corrispettivi(
        self, db_session, fiscal_service, tax, repo
    ):
        order, detail = seed_paid_order(
            db_session,
            tax,
            reference="RET-INV",
            order_date=datetime(2026, 7, 14, 10, 0, 0),
        )
        seed_invoice(db_session, order)

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

        movements = repo.fetch_movements(2026, 7)
        assert sum(m.returns_amount for m in movements) == Decimal("0")

    @pytest.mark.asyncio
    async def test_unpaid_order_return_not_in_corrispettivi(
        self, db_session, fiscal_service, tax, repo
    ):
        order, detail = seed_paid_order(
            db_session,
            tax,
            reference="RET-UNPAID",
            order_date=datetime(2026, 7, 16, 10, 0, 0),
            is_payed=False,
        )

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

        movements = repo.fetch_movements(2026, 7)
        assert sum(m.sales_amount for m in movements) == Decimal("0")
        assert sum(m.returns_amount for m in movements) == Decimal("0")
