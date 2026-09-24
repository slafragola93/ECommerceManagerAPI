"""Test create_invoice: residuo, parziale, riemissione."""
from datetime import datetime
from decimal import Decimal

import pytest

from src.models.address import Address
from src.models.customer import Customer
from src.models.fiscal_document_detail import FiscalDocumentDetail
from src.models.order_detail import OrderDetail
from src.repository.fiscal_document_repository import FiscalDocumentRepository
from tests.helpers.fiscal_test_helpers import seed_country, seed_paid_order, seed_tax


@pytest.fixture
def repo(db_session):
    return FiscalDocumentRepository(db_session)


@pytest.fixture
def tax(db_session):
    return seed_tax(db_session)


def _attach_invoice_address(db_session, order):
    country = seed_country(db_session, iso_code="IT", name="Italia")
    customer = (
        db_session.query(Customer)
        .filter(Customer.id_customer == order.id_customer)
        .first()
    )
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
    order.id_address_invoice = address.id_address
    db_session.commit()
    return address


def _seed_order_two_lines(db_session, tax, *, product_qty=2, with_shipping=True):
    order, detail1 = seed_paid_order(
        db_session,
        tax,
        reference="INV-PARTIAL",
        order_date=datetime(2026, 7, 22, 10, 0, 0),
        with_shipping=with_shipping,
        product_qty=product_qty,
        unit_net=Decimal("100.00"),
        unit_gross=Decimal("122.00"),
        country_iso="IT",
    )
    detail2 = OrderDetail(
        id_order=order.id_order,
        id_tax=tax.id_tax,
        product_name="Prodotto B",
        product_qty=product_qty,
        unit_price_with_tax=Decimal("61.00"),
        unit_price_net=Decimal("50.00"),
        total_price_with_tax=Decimal("61.00") * product_qty,
        total_price_net=Decimal("50.00") * product_qty,
    )
    db_session.add(detail2)
    # aggiorna totali ordine
    shipping_net = Decimal("10.00") if with_shipping else Decimal("0")
    shipping_gross = Decimal("12.20") if with_shipping else Decimal("0")
    products_net = Decimal("100.00") * product_qty + Decimal("50.00") * product_qty
    products_gross = Decimal("122.00") * product_qty + Decimal("61.00") * product_qty
    order.products_total_price_net = products_net
    order.products_total_price_with_tax = products_gross
    order.total_price_net = products_net + shipping_net
    order.total_price_with_tax = products_gross + shipping_gross
    db_session.commit()
    db_session.refresh(detail2)
    _attach_invoice_address(db_session, order)
    return order, detail1, detail2


class TestCreateInvoiceResidual:
    def test_full_order_two_lines(self, db_session, repo, tax):
        order, d1, d2 = _seed_order_two_lines(db_session, tax, product_qty=2)
        invoice = repo.create_invoice(id_order=order.id_order)

        details = (
            db_session.query(FiscalDocumentDetail)
            .filter(
                FiscalDocumentDetail.id_fiscal_document == invoice.id_fiscal_document
            )
            .all()
        )
        assert len(details) == 2
        qty_by_od = {d.id_order_detail: float(d.product_qty) for d in details}
        assert qty_by_od[d1.id_order_detail] == 2.0
        assert qty_by_od[d2.id_order_detail] == 2.0
        assert invoice.includes_shipping is True
        assert float(invoice.products_total_price_net) == pytest.approx(300.0)
        assert float(invoice.total_price_net) == pytest.approx(310.0)


class TestCreateInvoicePartial:
    def test_partial_one_line_qty_less_than_residual(self, db_session, repo, tax):
        order, d1, d2 = _seed_order_two_lines(db_session, tax, product_qty=3)
        invoice = repo.create_invoice(
            id_order=order.id_order,
            is_partial=True,
            items=[{"id_order_detail": d1.id_order_detail, "quantity": 1}],
            include_shipping=False,
        )
        details = (
            db_session.query(FiscalDocumentDetail)
            .filter(
                FiscalDocumentDetail.id_fiscal_document == invoice.id_fiscal_document
            )
            .all()
        )
        assert len(details) == 1
        assert details[0].id_order_detail == d1.id_order_detail
        assert float(details[0].product_qty) == 1.0
        assert invoice.includes_shipping is False
        assert float(invoice.products_total_price_net) == pytest.approx(100.0)
        assert float(invoice.total_price_net) == pytest.approx(100.0)

    def test_second_post_on_residual_only(self, db_session, repo, tax):
        order, d1, d2 = _seed_order_two_lines(db_session, tax, product_qty=3)
        repo.create_invoice(
            id_order=order.id_order,
            is_partial=True,
            items=[{"id_order_detail": d1.id_order_detail, "quantity": 1}],
            include_shipping=False,
        )
        invoice2 = repo.create_invoice(id_order=order.id_order)

        details = (
            db_session.query(FiscalDocumentDetail)
            .filter(
                FiscalDocumentDetail.id_fiscal_document == invoice2.id_fiscal_document
            )
            .all()
        )
        qty_by_od = {d.id_order_detail: float(d.product_qty) for d in details}
        assert qty_by_od[d1.id_order_detail] == 2.0  # 3 - 1 already invoiced
        assert qty_by_od[d2.id_order_detail] == 3.0
        # spedizione non ancora fatturata → inclusa sul residuo
        assert invoice2.includes_shipping is True

    def test_partial_qty_over_residual_raises(self, db_session, repo, tax):
        order, d1, _ = _seed_order_two_lines(db_session, tax, product_qty=2)
        repo.create_invoice(
            id_order=order.id_order,
            is_partial=True,
            items=[{"id_order_detail": d1.id_order_detail, "quantity": 1}],
            include_shipping=False,
        )
        with pytest.raises(ValueError) as exc:
            repo.create_invoice(
                id_order=order.id_order,
                is_partial=True,
                items=[{"id_order_detail": d1.id_order_detail, "quantity": 5}],
                include_shipping=False,
            )
        msg = str(exc.value)
        assert "residua" in msg.lower() or "superiore" in msg.lower()
        assert str(d1.id_order_detail) in msg

    def test_alien_order_detail_raises(self, db_session, repo, tax):
        order, d1, _ = _seed_order_two_lines(db_session, tax)
        other, other_d = seed_paid_order(
            db_session,
            tax,
            reference="OTHER-ORD",
            order_date=datetime(2026, 7, 23, 10, 0, 0),
            product_qty=1,
            country_iso="IT",
        )
        _attach_invoice_address(db_session, other)
        with pytest.raises(ValueError) as exc:
            repo.create_invoice(
                id_order=order.id_order,
                is_partial=True,
                items=[
                    {"id_order_detail": other_d.id_order_detail, "quantity": 1}
                ],
            )
        assert "non appartiene" in str(exc.value).lower()


class TestCreateInvoiceReemission:
    def test_reemission_with_items_ignores_residual_cap(self, db_session, repo, tax):
        order, d1, d2 = _seed_order_two_lines(db_session, tax, product_qty=2)
        # prima fattura piena sul residuo
        first = repo.create_invoice(id_order=order.id_order)
        assert first.includes_shipping is True

        # riemissione esplicita sulle stesse qty (senza is_partial)
        second = repo.create_invoice(
            id_order=order.id_order,
            is_partial=False,
            items=[
                {"id_order_detail": d1.id_order_detail, "quantity": 2},
                {"id_order_detail": d2.id_order_detail, "quantity": 2},
            ],
            include_shipping=False,
        )
        details = (
            db_session.query(FiscalDocumentDetail)
            .filter(
                FiscalDocumentDetail.id_fiscal_document == second.id_fiscal_document
            )
            .all()
        )
        assert len(details) == 2
        assert second.includes_shipping is False
        assert float(second.products_total_price_net) == pytest.approx(300.0)
