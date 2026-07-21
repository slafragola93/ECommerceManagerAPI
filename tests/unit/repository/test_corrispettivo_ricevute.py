"""BE-3.1 — Corrispettivi: decurtazione/imputazione ricevute emesse."""
from datetime import date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import func

from src.models.customer import Customer
from src.models.order import Order
from src.models.order_detail import OrderDetail
from src.models.ricevuta import Ricevuta, RicevutaStato
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


def _add_order_with_ricevuta(
    db_session,
    tax,
    *,
    reference: str,
    order_date: datetime,
    payment_date: date,
    emission_date: date,
    incasso_date: date,
    ricevuta_stato: RicevutaStato = RicevutaStato.EMESSA,
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
        payment_date=payment_date,
        is_payed=True,
        total_price_with_tax=Decimal("122.00"),
        total_price_net=Decimal("100.00"),
        products_total_price_with_tax=Decimal("122.00"),
        products_total_price_net=Decimal("100.00"),
    )
    db_session.add(order)
    db_session.commit()
    db_session.refresh(order)

    db_session.add(
        OrderDetail(
            id_order=order.id_order,
            id_tax=tax.id_tax,
            product_name="Prodotto test",
            product_qty=1,
            unit_price_with_tax=Decimal("122.00"),
            unit_price_net=Decimal("100.00"),
            total_price_with_tax=Decimal("122.00"),
            total_price_net=Decimal("100.00"),
        )
    )
    db_session.add(
        Ricevuta(
            numero=1,
            anno=emission_date.year,
            id_order=order.id_order,
            id_customer=customer.id_customer,
            data_incasso=incasso_date,
            data_emissione=datetime.combine(emission_date, datetime.min.time()),
            stato=ricevuta_stato,
        )
    )
    db_session.commit()
    return order


class TestCorrispettivoRicevute:
    def test_emessa_ricevuta_excluded_from_order_date_sales(self, db_session, repo, tax):
        _add_order_with_ricevuta(
            db_session,
            tax,
            reference="RICE-1",
            order_date=datetime(2026, 7, 1, 10, 0, 0),
            payment_date=date(2026, 7, 3),
            incasso_date=date(2026, 7, 3),
            emission_date=date(2026, 7, 8),
        )

        movements = repo.fetch_movements(2026, 7)
        sales_by_day = {}
        for movement in movements:
            if movement.sales_amount:
                sales_by_day.setdefault(movement.movement_date, Decimal("0"))
                sales_by_day[movement.movement_date] += movement.sales_amount

        assert sales_by_day.get(date(2026, 7, 1)) is None
        assert sales_by_day.get(date(2026, 7, 3)) is None
        assert sales_by_day.get(date(2026, 7, 8)) == Decimal("122.00")

    def test_annullata_ricevuta_restores_order_date_sales(self, db_session, repo, tax):
        _add_order_with_ricevuta(
            db_session,
            tax,
            reference="RICE-ANN",
            order_date=datetime(2026, 7, 10, 10, 0, 0),
            payment_date=date(2026, 7, 10),
            incasso_date=date(2026, 7, 10),
            emission_date=date(2026, 7, 12),
            ricevuta_stato=RicevutaStato.ANNULLATA,
        )

        movements = repo.fetch_movements(2026, 7)
        sales_amount = sum(m.sales_amount for m in movements)

        assert sales_amount == Decimal("122.00")

    def test_order_without_ricevuta_unchanged(self, db_session, repo, tax):
        order = Order(
            id_order_state=1,
            reference="PLAIN",
            date_add=datetime(2026, 7, 15, 12, 0, 0),
            is_payed=True,
            total_price_with_tax=Decimal("122.00"),
            total_price_net=Decimal("100.00"),
            products_total_price_with_tax=Decimal("122.00"),
            products_total_price_net=Decimal("100.00"),
        )
        db_session.add(order)
        db_session.commit()
        db_session.refresh(order)
        db_session.add(
            OrderDetail(
                id_order=order.id_order,
                id_tax=tax.id_tax,
                product_name="Prodotto test",
                product_qty=1,
                unit_price_with_tax=Decimal("122.00"),
                unit_price_net=Decimal("100.00"),
                total_price_with_tax=Decimal("122.00"),
                total_price_net=Decimal("100.00"),
            )
        )
        db_session.commit()

        movements = repo.fetch_movements(2026, 7)
        sales_amount = sum(m.sales_amount for m in movements)

        assert sales_amount == Decimal("122.00")

    def test_gross_totals_reflect_ricevuta_adjustments(self, db_session, repo, tax):
        _add_order_with_ricevuta(
            db_session,
            tax,
            reference="RICE-GROSS",
            order_date=datetime(2026, 7, 1, 10, 0, 0),
            payment_date=date(2026, 7, 3),
            incasso_date=date(2026, 7, 3),
            emission_date=date(2026, 7, 8),
        )

        totals = repo.fetch_daily_gross_totals(2026, 7)

        assert date(2026, 7, 1) not in totals
        assert totals[date(2026, 7, 8)]["sales"]["total_with_tax"] == Decimal("122.00")

    def test_sales_gross_breakdown_union_all(self, db_session, repo, tax):
        _add_order_with_ricevuta(
            db_session,
            tax,
            reference="RICE-BRK",
            order_date=datetime(2026, 7, 1, 10, 0, 0),
            payment_date=date(2026, 7, 3),
            incasso_date=date(2026, 7, 3),
            emission_date=date(2026, 7, 8),
        )

        breakdown = repo.fetch_sales_gross_breakdown_by_day(
            date(2026, 7, 1),
            date(2026, 7, 31),
        )

        assert date(2026, 7, 1) not in breakdown
        assert breakdown[date(2026, 7, 8)]["ricevute_decurtazione"]["total_with_tax"] == Decimal(
            "0"
        )
        assert breakdown[date(2026, 7, 8)]["ricevute_imputazione"]["total_with_tax"] == Decimal(
            "122.00"
        )
        assert breakdown[date(2026, 7, 8)]["net"]["total_with_tax"] == Decimal("122.00")

    def test_daily_gross_totals_include_sales_breakdown(self, db_session, repo, tax):
        _add_order_with_ricevuta(
            db_session,
            tax,
            reference="RICE-DAY",
            order_date=datetime(2026, 7, 1, 10, 0, 0),
            payment_date=date(2026, 7, 3),
            incasso_date=date(2026, 7, 3),
            emission_date=date(2026, 7, 8),
        )

        totals = repo.fetch_daily_gross_totals(2026, 7)
        day = totals[date(2026, 7, 8)]

        assert "sales_breakdown" in day
        assert day["sales_breakdown"]["ricevute_imputazione"]["total_with_tax"] == Decimal(
            "122.00"
        )
        assert day["sales"]["total_with_tax"] == Decimal("122.00")

    def test_return_on_order_with_ricevuta_still_counted(self, db_session, repo, tax):
        from src.models.fiscal_document import FiscalDocument
        from src.models.fiscal_document_detail import FiscalDocumentDetail

        order = _add_order_with_ricevuta(
            db_session,
            tax,
            reference="RICE-RET",
            order_date=datetime(2026, 7, 5, 10, 0, 0),
            payment_date=date(2026, 7, 5),
            incasso_date=date(2026, 7, 5),
            emission_date=date(2026, 7, 20),
        )
        detail = (
            db_session.query(OrderDetail)
            .filter(OrderDetail.id_order == order.id_order)
            .one()
        )
        return_doc = FiscalDocument(
            document_type="return",
            id_order=order.id_order,
            status="issued",
            date_add=datetime(2026, 7, 25, 12, 0, 0),
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

        movements = repo.fetch_movements(2026, 7)
        returns_amount = sum(m.returns_amount for m in movements)

        assert returns_amount == Decimal("36.60")

    def test_same_day_order_and_emission_stays_in_base(self, db_session, repo, tax):
        """Se date_add == data_emissione, l'ordine resta nelle vendite base del giorno ordine."""
        _add_order_with_ricevuta(
            db_session,
            tax,
            reference="RICE-SAME-DAY",
            order_date=datetime(2026, 7, 9, 10, 0, 0),
            payment_date=date(2026, 7, 9),
            incasso_date=date(2026, 7, 9),
            emission_date=date(2026, 7, 9),
        )

        breakdown = repo.fetch_sales_gross_breakdown_by_day(
            date(2026, 7, 1),
            date(2026, 7, 31),
        )
        day = breakdown[date(2026, 7, 9)]

        assert day["base"]["total_with_tax"] == Decimal("122.00")
        assert day["ricevute_decurtazione"]["total_with_tax"] == Decimal("0")
        assert day["ricevute_imputazione"]["total_with_tax"] == Decimal("0")
        assert day["net"]["total_with_tax"] == Decimal("122.00")

        totals = repo.fetch_daily_gross_totals(2026, 7)
        assert totals[date(2026, 7, 9)]["sales"]["total_with_tax"] == Decimal("122.00")

    def test_same_day_ricevuta_with_delayed_ricevuta_on_same_emission_day(
        self, db_session, repo, tax
    ):
        """Due ricevute emesse lo stesso giorno: quella same-day non si annulla."""
        _add_order_with_ricevuta(
            db_session,
            tax,
            reference="RICE-LATE",
            order_date=datetime(2026, 7, 1, 10, 0, 0),
            payment_date=date(2026, 7, 3),
            incasso_date=date(2026, 7, 3),
            emission_date=date(2026, 7, 9),
        )
        customer = Customer(
            id_lang=1,
            firstname="Luigi",
            lastname="Verdi",
            email="same-em@example.com",
        )
        db_session.add(customer)
        db_session.commit()
        db_session.refresh(customer)
        order2 = Order(
            id_customer=customer.id_customer,
            id_order_state=1,
            reference="RICE-TODAY",
            date_add=datetime(2026, 7, 9, 11, 0, 0),
            payment_date=date(2026, 7, 9),
            is_payed=True,
            total_price_with_tax=Decimal("50.00"),
            total_price_net=Decimal("40.00"),
            products_total_price_with_tax=Decimal("50.00"),
            products_total_price_net=Decimal("40.00"),
        )
        db_session.add(order2)
        db_session.commit()
        db_session.refresh(order2)
        db_session.add(
            OrderDetail(
                id_order=order2.id_order,
                id_tax=tax.id_tax,
                product_name="Prodotto B",
                product_qty=1,
                unit_price_with_tax=Decimal("50.00"),
                unit_price_net=Decimal("40.00"),
                total_price_with_tax=Decimal("50.00"),
                total_price_net=Decimal("40.00"),
            )
        )
        db_session.add(
            Ricevuta(
                numero=2,
                anno=2026,
                id_order=order2.id_order,
                id_customer=customer.id_customer,
                data_incasso=date(2026, 7, 9),
                data_emissione=datetime(2026, 7, 9, 12, 0),
                stato=RicevutaStato.EMESSA,
            )
        )
        db_session.commit()

        breakdown = repo.fetch_sales_gross_breakdown_by_day(
            date(2026, 7, 1),
            date(2026, 7, 31),
        )
        day = breakdown[date(2026, 7, 9)]

        assert day["base"]["total_with_tax"] == Decimal("50.00")
        assert day["ricevute_imputazione"]["total_with_tax"] == Decimal("122.00")
        assert day["ricevute_decurtazione"]["total_with_tax"] == Decimal("0")
        assert day["net"]["total_with_tax"] == Decimal("172.00")
        assert date(2026, 7, 1) not in breakdown

    def test_deferred_ricevuta_imputazione_with_shipping_and_multiple_lines(
        self, db_session, repo, tax
    ):
        """Ordine multi-riga + spedizione: imputazione solo su emissione, niente storno negativo."""
        shipping = Shipping(
            price_tax_incl=Decimal("20.00"),
            price_tax_excl=Decimal("16.39"),
            id_tax=tax.id_tax,
        )
        db_session.add(shipping)
        db_session.commit()
        db_session.refresh(shipping)

        customer = Customer(
            id_lang=1,
            firstname="Anna",
            lastname="Bianchi",
            email="multi-line@example.com",
        )
        db_session.add(customer)
        db_session.commit()
        db_session.refresh(customer)

        order = Order(
            id_customer=customer.id_customer,
            id_order_state=1,
            reference="RICE-MULTI",
            date_add=datetime(2026, 7, 15, 10, 0, 0),
            payment_date=date(2026, 7, 15),
            is_payed=True,
            id_shipping=shipping.id_shipping,
            total_price_with_tax=Decimal("309.97"),
            total_price_net=Decimal("254.07"),
            products_total_price_with_tax=Decimal("289.97"),
            products_total_price_net=Decimal("237.68"),
        )
        db_session.add(order)
        db_session.commit()
        db_session.refresh(order)

        for idx, gross in enumerate(
            (Decimal("100.00"), Decimal("89.97"), Decimal("100.00")), start=1
        ):
            net = (gross / Decimal("1.22")).quantize(Decimal("0.01"))
            db_session.add(
                OrderDetail(
                    id_order=order.id_order,
                    id_tax=tax.id_tax,
                    product_name=f"Prodotto {idx}",
                    product_qty=1,
                    unit_price_with_tax=gross,
                    unit_price_net=net,
                    total_price_with_tax=gross,
                    total_price_net=net,
                )
            )
        db_session.add(
            Ricevuta(
                numero=6,
                anno=2026,
                id_order=order.id_order,
                id_customer=customer.id_customer,
                data_incasso=date(2026, 7, 15),
                data_emissione=datetime(2026, 7, 21, 12, 0),
                stato=RicevutaStato.EMESSA,
            )
        )
        db_session.commit()

        movements = repo.fetch_movements(2026, 7)
        sales_by_day: dict[date, dict[str, Decimal]] = {}
        for movement in movements:
            if not movement.sales_amount:
                continue
            bucket = sales_by_day.setdefault(
                movement.movement_date,
                {"products": Decimal("0"), "shipping": Decimal("0")},
            )
            if movement.is_shipping:
                bucket["shipping"] += movement.sales_amount
            else:
                bucket["products"] += movement.sales_amount

        assert date(2026, 7, 15) not in sales_by_day
        assert sales_by_day[date(2026, 7, 21)]["products"] == Decimal("289.97")
        assert sales_by_day[date(2026, 7, 21)]["shipping"] == Decimal("20.00")

        matrix = aggregate_matrix(movements)
        rows, _ = build_riepilogo_rows(matrix, 2026, 7, {tax.id_tax: tax})
        row_15 = next(row for row in rows if row["date"] == date(2026, 7, 15))
        row_21 = next(row for row in rows if row["date"] == date(2026, 7, 21))
        cell_15 = row_15["cells"][str(tax.id_tax)]
        cell_21 = row_21["cells"][str(tax.id_tax)]

        assert cell_15["products_sales"] == Decimal("0")
        assert cell_15["shipping_sales"] == Decimal("0")
        assert cell_15["products_returns"] == Decimal("0")
        assert cell_15["shipping_returns"] == Decimal("0")
        assert row_15["row_total"] == Decimal("0")

        assert cell_21["products_sales"] == Decimal("289.97")
        assert cell_21["shipping_sales"] == Decimal("20.00")
        assert row_21["row_total"] == Decimal("309.97")

        service = CorrispettivoService(db_session)
        riepilogo = service.get_riepilogo(2026, 7)
        day_21 = next(r for r in riepilogo.rows if r.date == date(2026, 7, 21))
        assert day_21.row_total == Decimal("309.97")
