"""Verifica filtro ordini non fatturati in CorrispettivoRepository."""
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
    is_payed: bool = True,
    movement_date: datetime = datetime(2026, 7, 15, 12, 0, 0),
):
    order = Order(
        id_order_state=1,
        reference=reference,
        date_add=movement_date,
        is_payed=is_payed,
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


def _add_order_with_delivery_country(
    db_session,
    tax,
    *,
    reference: str,
    country_iso: str,
    total_with_tax: str = "122.00",
    total_net: str = "100.00",
    movement_date: datetime = datetime(2026, 7, 15, 12, 0, 0),
):
    country = (
        db_session.query(Country)
        .filter(func.upper(Country.iso_code) == country_iso.upper())
        .first()
    )
    if not country:
        country = Country(
            id_origin=hash(country_iso) % 100000,
            name=country_iso,
            iso_code=country_iso,
        )
        db_session.add(country)
        db_session.commit()
        db_session.refresh(country)

    address = Address(
        id_country=country.id_country,
        firstname="Test",
        lastname=country_iso,
        address1="Via test 1",
        city="City",
        postcode="00000",
        date_add=date.today(),
    )
    db_session.add(address)
    db_session.commit()
    db_session.refresh(address)

    order = Order(
        id_order_state=1,
        reference=reference,
        date_add=movement_date,
        is_payed=True,
        id_address_delivery=address.id_address,
        total_price_with_tax=Decimal(total_with_tax),
        total_price_net=Decimal(total_net),
        products_total_price_with_tax=Decimal(total_with_tax),
        products_total_price_net=Decimal(total_net),
    )
    db_session.add(order)
    db_session.commit()
    db_session.refresh(order)

    db_session.add(
        OrderDetail(
            id_order=order.id_order,
            id_tax=tax.id_tax,
            product_name=f"Prodotto {reference}",
            product_qty=1,
            unit_price_with_tax=Decimal(total_with_tax),
            unit_price_net=Decimal(total_net),
            total_price_with_tax=Decimal(total_with_tax),
            total_price_net=Decimal(total_net),
        )
    )
    db_session.commit()
    return order


class TestCorrispettivoNoInvoiceFilter:
    def test_sales_exclude_invoiced_orders(self, db_session, repo, tax):
        _add_order(db_session, tax, reference="NO-INV")
        _add_order(db_session, tax, reference="WITH-INV", with_invoice=True)

        movements = repo.fetch_movements(2026, 7)
        sales_amount = sum(m.sales_amount for m in movements)

        assert sales_amount == Decimal("122.00")

        counts = repo.fetch_daily_counts(2026, 7)
        assert sum(order_count for order_count, _ in counts.values()) == 1

    def test_sales_include_order_with_credit_note_only(self, db_session, repo, tax):
        _add_order(db_session, tax, reference="CN-ONLY", with_credit_note=True)

        movements = repo.fetch_movements(2026, 7)
        sales_amount = sum(m.sales_amount for m in movements)

        assert sales_amount == Decimal("122.00")

    def test_returns_excluded_on_invoiced_order_without_credit_note(
        self, db_session, repo, tax
    ):
        _add_order(db_session, tax, reference="RET-OK", with_return=True)
        _add_order(
            db_session,
            tax,
            reference="RET-INV",
            with_invoice=True,
            with_return=True,
        )

        movements = repo.fetch_movements(2026, 7)
        returns_amount = sum(m.returns_amount for m in movements)

        assert returns_amount == Decimal("36.60")

    def test_returns_included_on_invoiced_order_with_credit_note(
        self, db_session, repo, tax
    ):
        _add_order(
            db_session,
            tax,
            reference="RET-INV-CN",
            with_invoice=True,
            with_credit_note=True,
            with_return=True,
        )

        movements = repo.fetch_movements(2026, 7)
        returns_amount = sum(m.returns_amount for m in movements)

        assert returns_amount == Decimal("36.60")

    def test_sales_exclude_unpaid_orders(self, db_session, repo, tax):
        _add_order(db_session, tax, reference="PAID", is_payed=True)
        _add_order(db_session, tax, reference="UNPAID", is_payed=False)

        movements = repo.fetch_movements(2026, 7)
        sales_amount = sum(m.sales_amount for m in movements)

        assert sales_amount == Decimal("122.00")

    def test_no_invoice_filter_matches_order_repository_semantics(self, db_session, repo, tax):
        """Stesso criterio di OrderRepository.has_invoice=false + is_payed=true."""
        included = _add_order(db_session, tax, reference="IN", is_payed=True)
        excluded_invoice = _add_order(db_session, tax, reference="OUT", with_invoice=True)
        excluded_unpaid = _add_order(db_session, tax, reference="UNPAID", is_payed=False)

        order_day = repo._local_day_expr(Order.date_add)
        ids = {
            row[0]
            for row in db_session.query(Order.id_order)
            .filter(
                *repo._corrispettivi_sales_order_filters(),
                order_day >= datetime(2026, 7, 1).date(),
                order_day <= datetime(2026, 7, 31).date(),
            )
            .all()
        }

        assert included.id_order in ids
        assert excluded_invoice.id_order not in ids
        assert excluded_unpaid.id_order not in ids


class TestCorrispettivoDeliveryCountryFilter:
    def test_fetch_daily_gross_totals_filters_by_delivery_country(
        self, db_session, repo, tax
    ):
        _add_order_with_delivery_country(
            db_session, tax, reference="IT-1", country_iso="IT"
        )
        _add_order_with_delivery_country(
            db_session,
            tax,
            reference="FR-1",
            country_iso="FR",
            total_with_tax="200.00",
            total_net="163.93",
        )

        all_totals = repo.fetch_daily_gross_totals(2026, 7)
        it_totals = repo.fetch_daily_gross_totals(
            2026, 7, {"delivery_country_iso": "IT"}
        )
        fr_totals = repo.fetch_daily_gross_totals(
            2026, 7, {"delivery_country_iso": "FR"}
        )

        movement_date = datetime(2026, 7, 15).date()
        all_sales = all_totals[movement_date]["sales"]["total_with_tax"]
        it_sales = it_totals[movement_date]["sales"]["total_with_tax"]
        fr_sales = fr_totals[movement_date]["sales"]["total_with_tax"]

        assert all_sales == Decimal("322.00")
        assert it_sales == Decimal("122.00")
        assert fr_sales == Decimal("200.00")

    def test_fetch_movements_filters_by_delivery_country(self, db_session, repo, tax):
        _add_order_with_delivery_country(
            db_session, tax, reference="IT-2", country_iso="IT"
        )
        _add_order_with_delivery_country(
            db_session,
            tax,
            reference="FR-2",
            country_iso="FR",
            total_with_tax="50.00",
            total_net="40.98",
        )

        it_movements = repo.fetch_movements(
            2026, 7, {"delivery_country_iso": "IT"}
        )
        fr_movements = repo.fetch_movements(
            2026, 7, {"delivery_country_iso": "FR"}
        )

        assert sum(m.sales_amount for m in it_movements) == Decimal("122.00")
        assert sum(m.sales_amount for m in fr_movements) == Decimal("50.00")

    def test_list_country_codes_with_movements(self, db_session, repo, tax):
        _add_order_with_delivery_country(
            db_session, tax, reference="IT-3", country_iso="IT"
        )
        _add_order_with_delivery_country(
            db_session, tax, reference="FR-3", country_iso="FR"
        )

        codes = repo.list_country_codes_with_movements(2026, 7)

        assert codes == ["FR", "IT"]
