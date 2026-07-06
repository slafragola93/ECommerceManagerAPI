"""Verifica filtro ordini non fatturati in CorrispettivoRepository."""
from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy import func

from src.models.fiscal_document import FiscalDocument
from src.models.fiscal_document_detail import FiscalDocumentDetail
from src.models.order import Order
from src.models.order_detail import OrderDetail
from src.models.tax import Tax
from src.repository.corrispettivo_repository import CorrispettivoRepository


@pytest.fixture(autouse=True)
def sqlite_local_day(monkeypatch):
    """SQLite non supporta convert_tz: usa date() semplice nei test."""
    monkeypatch.setattr(
        CorrispettivoRepository,
        "_local_day_expr",
        lambda self, column: func.date(column),
    )


@pytest.fixture
def tax(db_session):
    row = Tax(name="IVA 22%", percentage=22, code="22", is_default=0)
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    return row


@pytest.fixture
def repo(db_session):
    return CorrispettivoRepository(db_session)


def _add_order(
    db_session,
    tax,
    *,
    reference: str,
    with_invoice: bool = False,
    with_credit_note: bool = False,
    with_return: bool = False,
    movement_date: datetime = datetime(2026, 7, 15, 12, 0, 0),
):
    order = Order(
        id_order_state=1,
        reference=reference,
        date_add=movement_date,
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
        product_name="Prodotto test",
        product_qty=1,
        unit_price_with_tax=Decimal("122.00"),
        unit_price_net=Decimal("100.00"),
        total_price_with_tax=Decimal("122.00"),
        total_price_net=Decimal("100.00"),
    )
    db_session.add(detail)
    db_session.commit()
    db_session.refresh(detail)

    if with_invoice:
        db_session.add(
            FiscalDocument(
                document_type="invoice",
                id_order=order.id_order,
                status="issued",
                total_price_net=Decimal("100.00"),
                total_price_with_tax=Decimal("122.00"),
            )
        )
    if with_credit_note:
        db_session.add(
            FiscalDocument(
                document_type="credit_note",
                id_order=order.id_order,
                status="issued",
                total_price_net=Decimal("50.00"),
                total_price_with_tax=Decimal("61.00"),
            )
        )
    if with_return:
        return_doc = FiscalDocument(
            document_type="return",
            id_order=order.id_order,
            status="issued",
            date_add=movement_date,
            total_price_net=Decimal("30.00"),
            total_price_with_tax=Decimal("36.60"),
            products_total_price_net=Decimal("30.00"),
            products_total_price_with_tax=Decimal("36.60"),
        )
        db_session.add(return_doc)
        db_session.commit()
        db_session.refresh(return_doc)
        db_session.add(
            FiscalDocumentDetail(
                id_fiscal_document=return_doc.id_fiscal_document,
                id_order_detail=detail.id_order_detail,
                product_qty=1,
                id_tax=tax.id_tax,
                unit_price_with_tax=Decimal("36.60"),
                total_price_with_tax=Decimal("36.60"),
                total_price_net=Decimal("30.00"),
            )
        )

    db_session.commit()
    return order


class TestCorrispettivoNoInvoiceFilter:
    def test_sales_exclude_invoiced_orders(self, db_session, repo, tax):
        _add_order(db_session, tax, reference="NO-INV")
        _add_order(db_session, tax, reference="WITH-INV", with_invoice=True)

        movements = repo.fetch_movements(2026, 7)
        sales_net = sum(m.sales_net for m in movements)

        assert sales_net == Decimal("100.00")

        counts = repo.fetch_daily_counts(2026, 7)
        assert sum(order_count for order_count, _ in counts.values()) == 1

    def test_sales_include_order_with_credit_note_only(self, db_session, repo, tax):
        _add_order(db_session, tax, reference="CN-ONLY", with_credit_note=True)

        movements = repo.fetch_movements(2026, 7)
        sales_net = sum(m.sales_net for m in movements)

        assert sales_net == Decimal("100.00")

    def test_returns_only_on_non_invoiced_orders(self, db_session, repo, tax):
        _add_order(db_session, tax, reference="RET-OK", with_return=True)
        _add_order(
            db_session,
            tax,
            reference="RET-INV",
            with_invoice=True,
            with_return=True,
        )

        movements = repo.fetch_movements(2026, 7)
        returns_net = sum(m.returns_net for m in movements)

        assert returns_net == Decimal("30.00")

    def test_no_invoice_filter_matches_order_repository_semantics(self, db_session, repo, tax):
        """Stesso criterio di OrderRepository.has_invoice=false."""
        included = _add_order(db_session, tax, reference="IN")
        excluded = _add_order(db_session, tax, reference="OUT", with_invoice=True)

        order_day = repo._local_day_expr(Order.date_add)
        ids = {
            row[0]
            for row in db_session.query(Order.id_order)
            .filter(
                repo._no_invoice_filter(),
                order_day >= datetime(2026, 7, 1).date(),
                order_day <= datetime(2026, 7, 31).date(),
            )
            .all()
        }

        assert included.id_order in ids
        assert excluded.id_order not in ids
