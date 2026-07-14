"""Resi con spedizione nel corrispettivo riepilogo."""
from datetime import date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import func

from src.models.address import Address
from src.models.country import Country
from src.models.fiscal_document import FiscalDocument
from src.models.fiscal_document_detail import FiscalDocumentDetail
from src.models.order import Order
from src.models.order_detail import OrderDetail
from src.models.shipping import Shipping
from src.models.tax import Tax
from src.repository.corrispettivo_repository import CorrispettivoRepository
from src.services.corrispettivi.aggregation import aggregate_matrix, build_riepilogo_rows
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


def _add_order_with_shipping_return(db_session, tax):
    country = Country(id_origin=1, name="Italia", iso_code="IT")
    db_session.add(country)
    db_session.commit()
    db_session.refresh(country)

    address = Address(
        id_country=country.id_country,
        firstname="Test",
        lastname="User",
        address1="Via 1",
        city="Roma",
        postcode="00100",
        date_add=date.today(),
    )
    db_session.add(address)
    db_session.commit()
    db_session.refresh(address)

    shipping = Shipping(
        id_tax=tax.id_tax,
        price_tax_incl=Decimal("12.20"),
        price_tax_excl=Decimal("10.00"),
    )
    db_session.add(shipping)
    db_session.commit()
    db_session.refresh(shipping)

    movement_date = datetime(2026, 7, 15, 12, 0, 0)
    order = Order(
        id_order_state=1,
        reference="RET-SHIP",
        date_add=movement_date,
        is_payed=True,
        id_address_delivery=address.id_address,
        id_shipping=shipping.id_shipping,
        total_price_with_tax=Decimal("134.20"),
        total_price_net=Decimal("110.00"),
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

    return_doc = FiscalDocument(
        document_type="return",
        id_order=order.id_order,
        status="issued",
        date_add=movement_date,
        includes_shipping=True,
        total_price_net=Decimal("40.00"),
        total_price_with_tax=Decimal("48.80"),
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
    return order, shipping, return_doc


class TestCorrispettivoReturnShipping:
    def test_fetch_movements_includes_shipping_return(self, db_session, repo, tax):
        _add_order_with_shipping_return(db_session, tax)

        movements = repo.fetch_movements(2026, 7)
        shipping_returns = [
            m for m in movements if m.is_shipping and m.returns_net
        ]
        product_returns = [
            m for m in movements if not m.is_shipping and m.returns_net
        ]

        assert sum(m.returns_net for m in product_returns) == Decimal("30.00")
        assert sum(m.returns_net for m in shipping_returns) == Decimal("10.00")

    def test_riepilogo_shipping_row_exposes_returns_net(self, db_session, repo, tax):
        _add_order_with_shipping_return(db_session, tax)

        service = CorrispettivoService(db_session)
        response = service.get_riepilogo(2026, 7)

        assert len(response.rows) == 1
        shipping = response.rows[0].shipping
        assert shipping.returns_net == Decimal("10.00")
        assert shipping.sales_net == Decimal("10.00")
        assert shipping.net == Decimal("0.00")

    def test_aggregate_matrix_shipping_returns(self, db_session, repo, tax):
        _add_order_with_shipping_return(db_session, tax)

        movements = repo.fetch_movements(2026, 7)
        product_buckets, shipping_buckets = aggregate_matrix(movements)
        day = datetime(2026, 7, 15).date()

        assert shipping_buckets[day].returns_net == Decimal("10.00")
        assert shipping_buckets[day].sales_net == Decimal("10.00")

        rows, _ = build_riepilogo_rows(product_buckets, shipping_buckets, {})
        assert rows[0]["shipping"]["returns_net"] == Decimal("10.00")

    def test_return_shipping_fallback_when_document_totals_missing(
        self, db_session, repo, tax
    ):
        """Reso con includes_shipping ma totali netti non valorizzati → fallback su spedizione ordine."""
        country = Country(id_origin=2, name="Italia", iso_code="IT")
        db_session.add(country)
        db_session.commit()
        db_session.refresh(country)

        address = Address(
            id_country=country.id_country,
            firstname="Test",
            lastname="User",
            address1="Via 1",
            city="Roma",
            postcode="00100",
            date_add=date.today(),
        )
        db_session.add(address)
        db_session.commit()
        db_session.refresh(address)

        shipping = Shipping(
            id_tax=tax.id_tax,
            price_tax_incl=Decimal("12.20"),
            price_tax_excl=Decimal("10.00"),
        )
        db_session.add(shipping)
        db_session.commit()
        db_session.refresh(shipping)

        movement_date = datetime(2026, 7, 16, 12, 0, 0)
        order = Order(
            id_order_state=1,
            reference="RET-SHIP-FALLBACK",
            date_add=movement_date,
            is_payed=True,
            id_address_delivery=address.id_address,
            id_shipping=shipping.id_shipping,
            total_price_with_tax=Decimal("134.20"),
            total_price_net=Decimal("110.00"),
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

        return_doc = FiscalDocument(
            document_type="return",
            id_order=order.id_order,
            status="issued",
            date_add=movement_date,
            includes_shipping=True,
            total_price_net=Decimal("0"),
            total_price_with_tax=Decimal("36.60"),
            products_total_price_net=Decimal("0"),
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

        movements = repo.fetch_movements(2026, 7)
        shipping_returns = sum(
            m.returns_net for m in movements if m.is_shipping and m.returns_net
        )

        assert shipping_returns == Decimal("10.00")
