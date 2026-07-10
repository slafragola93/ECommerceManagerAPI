"""BE-3.3 — Compatibilità corrispettivi: ricevute emesse + resi (incluso delete)."""
from datetime import date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import func

from src.models.customer import Customer
from src.models.fiscal_document import FiscalDocument
from src.models.fiscal_document_detail import FiscalDocumentDetail
from src.models.order import Order
from src.models.order_detail import OrderDetail
from src.models.ricevuta import Ricevuta, RicevutaStato
from src.models.tax import Tax
from src.repository.corrispettivo_repository import CorrispettivoRepository
from src.repository.fiscal_document_repository import FiscalDocumentRepository
from src.services.routers.corrispettivo_service import CorrispettivoService


@pytest.fixture(autouse=True)
def sqlite_local_day(monkeypatch):
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


@pytest.fixture
def fiscal_repo(db_session):
    return FiscalDocumentRepository(db_session)


def _sum_sales_net(movements) -> Decimal:
    return sum(m.sales_net for m in movements)


def _sum_returns_net(movements) -> Decimal:
    return sum(m.returns_net for m in movements)


def _add_paid_order(
    db_session,
    tax,
    *,
    reference: str,
    order_date: datetime,
    payment_date: date | None = None,
    with_ricevuta: bool = False,
    ricevuta_emission: date | None = None,
    ricevuta_incasso: date | None = None,
):
    customer = Customer(
        id_lang=1,
        firstname="Mario",
        lastname="Rossi",
        email=f"{reference}@example.com",
    )
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)

    order = Order(
        id_customer=customer.id_customer,
        id_order_state=1,
        reference=reference,
        date_add=order_date,
        payment_date=payment_date or order_date.date(),
        is_payed=True,
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

    if with_ricevuta:
        emission = ricevuta_emission or payment_date or order_date.date()
        incasso = ricevuta_incasso or payment_date or order_date.date()
        if isinstance(emission, date) and not isinstance(emission, datetime):
            emission = datetime.combine(emission, datetime.min.time())
        db_session.add(
            Ricevuta(
                numero=1,
                anno=emission.year,
                id_order=order.id_order,
                id_customer=customer.id_customer,
                data_incasso=incasso,
                data_emissione=emission,
                stato=RicevutaStato.EMESSA,
            )
        )
        db_session.commit()

    return order, detail


def _add_return(
    db_session,
    tax,
    order: Order,
    detail: OrderDetail,
    *,
    return_date: datetime,
    return_net: Decimal = Decimal("30.00"),
    return_gross: Decimal = Decimal("36.60"),
):
    return_doc = FiscalDocument(
        document_type="return",
        id_order=order.id_order,
        status="issued",
        date_add=return_date,
        total_price_net=return_net,
        total_price_with_tax=return_gross,
        products_total_price_net=return_net,
        products_total_price_with_tax=return_gross,
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
            unit_price_with_tax=return_gross,
            total_price_with_tax=return_gross,
            total_price_net=return_net,
        )
    )
    db_session.commit()
    return return_doc


class TestCorrispettivoRicevuteReturnsBE33:
    def test_ricevuta_and_return_same_order_both_included(self, db_session, repo, tax):
        order, detail = _add_paid_order(
            db_session,
            tax,
            reference="BOTH",
            order_date=datetime(2026, 7, 5, 10, 0, 0),
            payment_date=date(2026, 7, 5),
            with_ricevuta=True,
            ricevuta_incasso=date(2026, 7, 5),
            ricevuta_emission=date(2026, 7, 20),
        )
        _add_return(
            db_session,
            tax,
            order,
            detail,
            return_date=datetime(2026, 7, 25, 12, 0, 0),
        )

        movements = repo.fetch_movements(2026, 7)

        assert _sum_sales_net(movements) == Decimal("0.00")
        assert _sum_returns_net(movements) == Decimal("30.00")

    def test_delete_return_on_ricevuta_order_removes_only_return(
        self, db_session, repo, fiscal_repo, tax
    ):
        order, detail = _add_paid_order(
            db_session,
            tax,
            reference="DEL-RET-RICE",
            order_date=datetime(2026, 7, 5, 10, 0, 0),
            payment_date=date(2026, 7, 5),
            with_ricevuta=True,
            ricevuta_incasso=date(2026, 7, 5),
            ricevuta_emission=date(2026, 7, 20),
        )
        return_doc = _add_return(
            db_session,
            tax,
            order,
            detail,
            return_date=datetime(2026, 7, 25, 12, 0, 0),
        )

        before = repo.fetch_movements(2026, 7)
        assert _sum_returns_net(before) == Decimal("30.00")

        fiscal_repo.delete_fiscal_document(return_doc.id_fiscal_document)

        after = repo.fetch_movements(2026, 7)
        assert _sum_returns_net(after) == Decimal("0.00")
        assert _sum_sales_net(after) == _sum_sales_net(before)

    def test_delete_return_on_plain_order_keeps_order_date_sales(
        self, db_session, repo, fiscal_repo, tax
    ):
        order, detail = _add_paid_order(
            db_session,
            tax,
            reference="DEL-RET-PLAIN",
            order_date=datetime(2026, 7, 10, 10, 0, 0),
        )
        return_doc = _add_return(
            db_session,
            tax,
            order,
            detail,
            return_date=datetime(2026, 7, 22, 12, 0, 0),
        )

        with_return = repo.fetch_movements(2026, 7)
        assert _sum_sales_net(with_return) == Decimal("100.00")
        assert _sum_returns_net(with_return) == Decimal("30.00")

        fiscal_repo.delete_fiscal_document(return_doc.id_fiscal_document)

        after_delete = repo.fetch_movements(2026, 7)
        assert _sum_sales_net(after_delete) == Decimal("100.00")
        assert _sum_returns_net(after_delete) == Decimal("0.00")

        sales_by_day = {
            m.movement_date: m.sales_net
            for m in after_delete
            if m.sales_net and not m.is_shipping
        }
        assert sales_by_day.get(date(2026, 7, 10)) == Decimal("100.00")

    def test_delete_return_detail_partial_with_ricevuta(
        self, db_session, repo, fiscal_repo, tax
    ):
        order, detail = _add_paid_order(
            db_session,
            tax,
            reference="DEL-DET",
            order_date=datetime(2026, 7, 8, 10, 0, 0),
            with_ricevuta=True,
            ricevuta_incasso=date(2026, 7, 8),
            ricevuta_emission=date(2026, 7, 15),
        )
        return_doc = _add_return(
            db_session,
            tax,
            order,
            detail,
            return_date=datetime(2026, 7, 28, 12, 0, 0),
        )
        fd_detail = (
            db_session.query(FiscalDocumentDetail)
            .filter(
                FiscalDocumentDetail.id_fiscal_document
                == return_doc.id_fiscal_document
            )
            .one()
        )

        fiscal_repo.delete_fiscal_document_detail(fd_detail.id_fiscal_document_detail)

        movements = repo.fetch_movements(2026, 7)
        assert _sum_returns_net(movements) == Decimal("0.00")
        assert _sum_sales_net(movements) == Decimal("0.00")

    def test_annullata_ricevuta_after_return_delete_restores_date_add_sales(
        self, db_session, repo, fiscal_repo, tax
    ):
        order, detail = _add_paid_order(
            db_session,
            tax,
            reference="ANN-RICE",
            order_date=datetime(2026, 7, 12, 10, 0, 0),
            with_ricevuta=True,
            ricevuta_incasso=date(2026, 7, 12),
            ricevuta_emission=date(2026, 7, 18),
        )
        return_doc = _add_return(
            db_session,
            tax,
            order,
            detail,
            return_date=datetime(2026, 7, 30, 12, 0, 0),
        )
        fiscal_repo.delete_fiscal_document(return_doc.id_fiscal_document)

        ricevuta = (
            db_session.query(Ricevuta)
            .filter(Ricevuta.id_order == order.id_order)
            .one()
        )
        ricevuta.stato = RicevutaStato.ANNULLATA
        db_session.commit()

        movements = repo.fetch_movements(2026, 7)
        assert _sum_sales_net(movements) == Decimal("100.00")
        assert _sum_returns_net(movements) == Decimal("0.00")

    def test_daily_summary_net_after_return_delete_with_ricevuta(
        self, db_session, fiscal_repo, tax
    ):
        order, detail = _add_paid_order(
            db_session,
            tax,
            reference="SVC",
            order_date=datetime(2026, 7, 6, 10, 0, 0),
            with_ricevuta=True,
            ricevuta_incasso=date(2026, 7, 6),
            ricevuta_emission=date(2026, 7, 14),
        )
        return_doc = _add_return(
            db_session,
            tax,
            order,
            detail,
            return_date=datetime(2026, 7, 27, 12, 0, 0),
        )

        service = CorrispettivoService(db_session)
        with_return = service.get_daily_summary(2026, 7)
        month_net_with_return = with_return.month_totals.total_net

        fiscal_repo.delete_fiscal_document(return_doc.id_fiscal_document)

        after_delete = service.get_daily_summary(2026, 7)
        month_net_after = after_delete.month_totals.total_net

        assert month_net_with_return == Decimal("-30.00")
        assert month_net_after == Decimal("0.00")
