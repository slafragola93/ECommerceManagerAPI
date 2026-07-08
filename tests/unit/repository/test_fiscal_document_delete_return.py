"""Test eliminazione resi e regole delete documenti fiscali."""
from decimal import Decimal

import pytest

from src.core.exceptions import BusinessRuleException, NotFoundException
from src.models.fiscal_document import FiscalDocument
from src.models.fiscal_document_detail import FiscalDocumentDetail
from src.models.order import Order
from src.models.order_detail import OrderDetail
from src.models.tax import Tax
from src.repository.fiscal_document_repository import FiscalDocumentRepository
from src.services.routers.fiscal_document_service import FiscalDocumentService


@pytest.fixture
def fiscal_repo(db_session):
    return FiscalDocumentRepository(db_session)


@pytest.fixture
def fiscal_service(db_session, fiscal_repo):
    return FiscalDocumentService(
        fiscal_document_repository=fiscal_repo,
        order_repository=None,
        order_detail_repository=None,
    )


@pytest.fixture
def tax(db_session):
    row = Tax(name="IVA 22%", percentage=22, code="22", is_default=0)
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    return row


def _create_order_with_detail(db_session, tax):
    order = Order(
        id_order_state=1,
        total_price_with_tax=Decimal("122.00"),
        total_price_net=Decimal("100.00"),
        products_total_price_with_tax=Decimal("122.00"),
        products_total_price_net=Decimal("100.00"),
    )
    db_session.add(order)
    db_session.commit()
    db_session.refresh(order)
    detail = OrderDetail(
        id_order=order.id_order,
        id_tax=tax.id_tax,
        product_name="Prodotto",
        product_qty=1,
        unit_price_with_tax=Decimal("122.00"),
        unit_price_net=Decimal("100.00"),
        total_price_with_tax=Decimal("122.00"),
        total_price_net=Decimal("100.00"),
    )
    db_session.add(detail)
    db_session.commit()
    db_session.refresh(detail)
    return order, detail


class TestDeleteReturnRepository:
    def test_delete_issued_return(self, db_session, fiscal_repo, tax):
        order, _ = _create_order_with_detail(db_session, tax)
        return_doc = FiscalDocument(
            document_type="return",
            id_order=order.id_order,
            status="issued",
            total_price_with_tax=Decimal("50.00"),
        )
        db_session.add(return_doc)
        db_session.commit()

        assert fiscal_repo.delete_fiscal_document(return_doc.id_fiscal_document) is True
        assert (
            db_session.query(FiscalDocument)
            .filter(FiscalDocument.id_fiscal_document == return_doc.id_fiscal_document)
            .first()
            is None
        )

    def test_cannot_delete_issued_invoice(self, db_session, fiscal_repo, tax):
        order, _ = _create_order_with_detail(db_session, tax)
        invoice = FiscalDocument(
            document_type="invoice",
            id_order=order.id_order,
            status="issued",
        )
        db_session.add(invoice)
        db_session.commit()

        with pytest.raises(ValueError, match="già generato"):
            fiscal_repo.delete_fiscal_document(invoice.id_fiscal_document)

    def test_delete_return_detail_only(self, db_session, fiscal_repo, tax):
        order, order_detail = _create_order_with_detail(db_session, tax)
        return_doc = FiscalDocument(
            document_type="return",
            id_order=order.id_order,
            status="issued",
            total_price_with_tax=Decimal("50.00"),
        )
        db_session.add(return_doc)
        db_session.commit()
        db_session.refresh(return_doc)
        fd_detail = FiscalDocumentDetail(
            id_fiscal_document=return_doc.id_fiscal_document,
            id_order_detail=order_detail.id_order_detail,
            product_qty=1,
            id_tax=tax.id_tax,
            unit_price_with_tax=Decimal("50.00"),
            total_price_with_tax=Decimal("50.00"),
            total_price_net=Decimal("40.00"),
        )
        db_session.add(fd_detail)
        db_session.commit()
        db_session.refresh(fd_detail)

        assert fiscal_repo.delete_fiscal_document_detail(fd_detail.id_fiscal_document_detail)

    def test_cannot_delete_invoice_detail(self, db_session, fiscal_repo, tax):
        order, order_detail = _create_order_with_detail(db_session, tax)
        invoice = FiscalDocument(
            document_type="invoice",
            id_order=order.id_order,
            status="pending",
        )
        db_session.add(invoice)
        db_session.commit()
        db_session.refresh(invoice)
        fd_detail = FiscalDocumentDetail(
            id_fiscal_document=invoice.id_fiscal_document,
            id_order_detail=order_detail.id_order_detail,
            product_qty=1,
            id_tax=tax.id_tax,
            unit_price_with_tax=Decimal("50.00"),
            total_price_with_tax=Decimal("50.00"),
            total_price_net=Decimal("40.00"),
        )
        db_session.add(fd_detail)
        db_session.commit()
        db_session.refresh(fd_detail)

        with pytest.raises(ValueError, match="documento di reso"):
            fiscal_repo.delete_fiscal_document_detail(fd_detail.id_fiscal_document_detail)


class TestDeleteReturnService:
    @pytest.mark.asyncio
    async def test_delete_return_not_found_raises_404(self, fiscal_service):
        with pytest.raises(NotFoundException):
            await fiscal_service.delete_fiscal_document(999999)

    @pytest.mark.asyncio
    async def test_delete_issued_invoice_raises_business_rule(
        self, db_session, fiscal_service, tax
    ):
        order, _ = _create_order_with_detail(db_session, tax)
        invoice = FiscalDocument(
            document_type="invoice",
            id_order=order.id_order,
            status="issued",
        )
        db_session.add(invoice)
        db_session.commit()
        db_session.refresh(invoice)

        with pytest.raises(BusinessRuleException):
            await fiscal_service.delete_fiscal_document(invoice.id_fiscal_document)

    @pytest.mark.asyncio
    async def test_delete_issued_return_success(
        self, db_session, fiscal_service, tax
    ):
        order, _ = _create_order_with_detail(db_session, tax)
        return_doc = FiscalDocument(
            document_type="return",
            id_order=order.id_order,
            status="issued",
            total_price_with_tax=Decimal("30.00"),
        )
        db_session.add(return_doc)
        db_session.commit()
        db_session.refresh(return_doc)

        result = await fiscal_service.delete_fiscal_document(return_doc.id_fiscal_document)
        assert result is True
