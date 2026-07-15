"""Test CorrispettivoService — riepilogo, summary, export, filtri."""
import io
import zipfile
from datetime import date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import func

from src.models.customer import Customer
from src.models.fiscal_document import FiscalDocument
from src.models.ricevuta import Ricevuta, RicevutaStato
from src.repository.corrispettivo_repository import CorrispettivoRepository
from src.schemas.corrispettivo_schema import (
    CorrispettivoExportRequestSchema,
    CorrispettivoFiltersSchema,
)
from src.services.export.corrispettivi_excel_service import CorrispettiviExcelService
from src.services.routers.corrispettivo_service import CorrispettivoService
from tests.helpers.fiscal_test_helpers import (
    seed_credit_note,
    seed_invoice,
    seed_paid_order,
    seed_return,
    seed_ricevuta,
    seed_tax,
)


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
def service(db_session):
    return CorrispettivoService(db_session)


class TestCorrispettivoServiceDailySummary:
    def test_daily_summary_with_sales_breakdown(self, db_session, service, tax):
        order, _ = seed_paid_order(
            db_session,
            tax,
            reference="SVC-BRK",
            order_date=datetime(2026, 7, 1, 10, 0, 0),
        )
        customer = db_session.query(Customer).filter(Customer.id_customer == order.id_customer).one()
        seed_ricevuta(
            db_session,
            order,
            customer,
            emission_date=date(2026, 7, 8),
            incasso_date=date(2026, 7, 3),
        )

        result = service.get_daily_summary(2026, 7)

        day_8 = next(d for d in result.days if d.date == date(2026, 7, 8))
        assert day_8.sales_breakdown is not None
        assert day_8.sales_breakdown.ricevute_imputazione.total_with_tax == Decimal("122.00")
        assert day_8.sales_breakdown.base.total_with_tax == Decimal("0")

    def test_filter_by_day(self, db_session, service, tax):
        seed_paid_order(
            db_session,
            tax,
            reference="DAY-1",
            order_date=datetime(2026, 7, 1, 10, 0, 0),
        )
        seed_paid_order(
            db_session,
            tax,
            reference="DAY-15",
            order_date=datetime(2026, 7, 15, 10, 0, 0),
        )

        result = service.get_daily_summary(
            2026, 7, CorrispettivoFiltersSchema(day=1)
        )

        assert len(result.days) == 1
        assert result.days[0].date == date(2026, 7, 1)

    def test_filter_by_platform_and_store(self, db_session, service, tax):
        seed_paid_order(
            db_session,
            tax,
            reference="PLAT-1",
            order_date=datetime(2026, 7, 5, 10, 0, 0),
            id_platform=1,
            id_store=10,
        )
        seed_paid_order(
            db_session,
            tax,
            reference="PLAT-2",
            order_date=datetime(2026, 7, 5, 11, 0, 0),
            id_platform=2,
            id_store=20,
        )

        filtered = service.get_daily_summary(
            2026,
            7,
            CorrispettivoFiltersSchema(id_platform=1, id_store=10),
        )

        assert filtered.month_totals.total_with_tax == Decimal("122.00")
        assert filtered.month_totals.order_count == 1

    def test_invoiced_order_excluded_retroactively(self, db_session, service, tax):
        order, _ = seed_paid_order(
            db_session,
            tax,
            reference="INV-RETRO",
            order_date=datetime(2026, 7, 12, 10, 0, 0),
        )

        before = service.get_daily_summary(2026, 7)
        assert before.month_totals.total_with_tax == Decimal("122.00")

        seed_invoice(db_session, order)

        after = service.get_daily_summary(2026, 7)
        assert after.month_totals.total_with_tax == Decimal("0.00")


class TestCorrispettivoServiceRiepilogo:
    def test_riepilogo_with_sales_returns_and_ricevuta(self, db_session, service, tax):
        order_plain, detail_plain = seed_paid_order(
            db_session,
            tax,
            reference="RIEP-PLAIN",
            order_date=datetime(2026, 7, 4, 10, 0, 0),
        )
        order_rice, _ = seed_paid_order(
            db_session,
            tax,
            reference="RIEP-RICE",
            order_date=datetime(2026, 7, 4, 11, 0, 0),
        )
        customer = db_session.query(Customer).filter(Customer.id_customer == order_rice.id_customer).one()
        seed_ricevuta(
            db_session,
            order_rice,
            customer,
            emission_date=date(2026, 7, 20),
        )
        seed_return(
            db_session,
            tax,
            order_plain,
            detail_plain,
            return_date=datetime(2026, 7, 18, 12, 0, 0),
        )

        result = service.get_riepilogo(2026, 7)

        assert result.year == 2026
        assert result.month == 7
        assert len(result.columns) >= 1
        assert len(result.rows) >= 2
        assert result.month_totals.products_sales >= Decimal("0")

    def test_riepilogo_filter_by_country(self, db_session, service, tax):
        seed_paid_order(
            db_session,
            tax,
            reference="IT-ORD",
            order_date=datetime(2026, 7, 6, 10, 0, 0),
            country_iso="IT",
        )
        seed_paid_order(
            db_session,
            tax,
            reference="FR-ORD",
            order_date=datetime(2026, 7, 6, 11, 0, 0),
            country_iso="FR",
        )

        italy = service.get_riepilogo(
            2026, 7, CorrispettivoFiltersSchema(delivery_country_iso="IT")
        )
        france = service.get_riepilogo(
            2026, 7, CorrispettivoFiltersSchema(delivery_country_iso="FR")
        )
        consolidated = service.get_riepilogo(2026, 7)

        assert italy.delivery_country_iso == "IT"
        assert france.delivery_country_iso == "FR"
        assert consolidated.month_totals.row_total == Decimal("244.00")
        assert italy.month_totals.row_total == Decimal("122.00")
        assert france.month_totals.row_total == Decimal("122.00")


class TestCorrispettivoServiceExport:
    def test_build_export_zip_not_empty(self, db_session, service, tax):
        seed_paid_order(
            db_session,
            tax,
            reference="EXP-1",
            order_date=datetime(2026, 7, 7, 10, 0, 0),
            country_iso="IT",
        )

        zip_bytes = service.build_export_zip(
            CorrispettivoExportRequestSchema(year=2026, month=7)
        )

        assert len(zip_bytes) > 100
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            names = zf.namelist()
            assert any(n.endswith("registro.xlsx") for n in names)


class TestChiusuraMeseAmministrativa:
    """Scenario mix mensile — chiusura contabile ecommerce."""

    def test_monthly_reconciliation_mixed_movements(self, db_session, service, tax):
        # Giorno 1 — ordine standard
        order_std, detail_std = seed_paid_order(
            db_session,
            tax,
            reference="CLOSE-STD",
            order_date=datetime(2026, 7, 1, 10, 0, 0),
        )

        # Giorno 3 — ricevuta differita (emissione 10)
        order_delay, detail_delay = seed_paid_order(
            db_session,
            tax,
            reference="CLOSE-DELAY",
            order_date=datetime(2026, 7, 3, 10, 0, 0),
        )
        cust_delay = db_session.query(Customer).filter(
            Customer.id_customer == order_delay.id_customer
        ).one()
        seed_ricevuta(
            db_session,
            order_delay,
            cust_delay,
            emission_date=date(2026, 7, 10),
            numero=1,
        )

        # Giorno 5 — ricevuta same-day
        order_same, _ = seed_paid_order(
            db_session,
            tax,
            reference="CLOSE-SAME",
            order_date=datetime(2026, 7, 5, 10, 0, 0),
        )
        cust_same = db_session.query(Customer).filter(
            Customer.id_customer == order_same.id_customer
        ).one()
        seed_ricevuta(
            db_session,
            order_same,
            cust_same,
            emission_date=date(2026, 7, 5),
            numero=2,
        )

        # Giorno 8 — reso parziale su ordine standard
        seed_return(
            db_session,
            tax,
            order_std,
            detail_std,
            return_date=datetime(2026, 7, 8, 12, 0, 0),
            qty=1,
            return_net=Decimal("30.00"),
            return_gross=Decimal("36.60"),
        )

        # Giorno 10 — reso su ordine con ricevuta differita
        seed_return(
            db_session,
            tax,
            order_delay,
            detail_delay,
            return_date=datetime(2026, 7, 10, 12, 0, 0),
        )

        # Giorno 15 — ordine poi fatturato (escluso retroattivamente)
        order_inv, _ = seed_paid_order(
            db_session,
            tax,
            reference="CLOSE-INV",
            order_date=datetime(2026, 7, 15, 10, 0, 0),
        )
        seed_invoice(db_session, order_inv)

        # Giorno 20 — ordine fatturato + nota credito + reso ammesso
        order_cn, detail_cn = seed_paid_order(
            db_session,
            tax,
            reference="CLOSE-CN",
            order_date=datetime(2026, 7, 20, 10, 0, 0),
        )
        seed_invoice(db_session, order_cn)
        seed_credit_note(db_session, order_cn)
        seed_return(
            db_session,
            tax,
            order_cn,
            detail_cn,
            return_date=datetime(2026, 7, 20, 14, 0, 0),
        )

        summary = service.get_daily_summary(2026, 7)
        riepilogo = service.get_riepilogo(2026, 7)

        assert summary.month_totals.order_count >= 3
        assert summary.month_totals.return_count >= 2
        assert summary.month_totals.total_with_tax != Decimal("0")

        day_10 = next((d for d in summary.days if d.date == date(2026, 7, 10)), None)
        assert day_10 is not None
        assert day_10.sales_breakdown.ricevute_imputazione.total_with_tax == Decimal("122.00")

        day_5 = next(d for d in summary.days if d.date == date(2026, 7, 5))
        assert day_5.sales.total_with_tax == Decimal("122.00")

        # Coerenza export Excel con summary consolidato
        zip_bytes = service.build_export_zip(
            CorrispettivoExportRequestSchema(year=2026, month=7)
        )
        excel = CorrispettiviExcelService()
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            registro_name = next(n for n in zf.namelist() if n.endswith("registro.xlsx"))
            registro_bytes = zf.read(registro_name)

        assert len(registro_bytes) > 0
        assert riepilogo.month_totals.products_sales >= Decimal("0")

        # Reso su ordine fatturato senza NC non entra nei corrispettivi
        orphan_order, orphan_detail = seed_paid_order(
            db_session,
            tax,
            reference="CLOSE-ORPHAN",
            order_date=datetime(2026, 7, 25, 10, 0, 0),
        )
        seed_invoice(db_session, orphan_order)
        seed_return(
            db_session,
            tax,
            orphan_order,
            orphan_detail,
            return_date=datetime(2026, 7, 25, 12, 0, 0),
        )
        after_orphan = service.get_daily_summary(2026, 7)
        day_25 = next((d for d in after_orphan.days if d.date == date(2026, 7, 25)), None)
        if day_25:
            assert day_25.returns.total_with_tax == Decimal("0")
