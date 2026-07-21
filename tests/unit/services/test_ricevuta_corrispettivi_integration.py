"""Test integrazione service ricevuta → corrispettivi (BE-3.1)."""
from datetime import date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import func

from src.core.container_config import get_configured_container
from src.models.ricevuta import Ricevuta
from src.repository.corrispettivo_repository import CorrispettivoRepository
from src.schemas.ricevuta_schema import RicevutaCreateSchema, RicevutaUpdateSchema
from src.services.interfaces.ricevuta_service_interface import IRicevutaService
from src.services.routers.corrispettivo_service import CorrispettivoService
from tests.helpers.fiscal_test_helpers import seed_company_info, seed_paid_order, seed_tax


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
def company_info(db_session):
    seed_company_info(db_session)


@pytest.fixture
def ricevuta_service(db_session):
    container = get_configured_container()
    return container.resolve_with_session(IRicevutaService, db_session)


@pytest.fixture
def corrispettivo_service(db_session):
    return CorrispettivoService(db_session)


class TestRicevutaCorrispettiviIntegration:
    def test_create_ricevuta_shifts_corrispettivi(
        self, db_session, ricevuta_service, corrispettivo_service, tax, company_info
    ):
        order, _ = seed_paid_order(
            db_session,
            tax,
            reference="XMOD-CREATE",
            order_date=datetime(2026, 7, 2, 10, 0, 0),
            payment_date=date(2026, 7, 2),
        )

        before = corrispettivo_service.get_daily_summary(2026, 7)
        assert before.month_totals.total_with_tax == Decimal("122.00")

        ricevuta_service.create_ricevuta(
            RicevutaCreateSchema(id_order=order.id_order, data_emissione="2026-07-10"),
            user_id=1,
        )

        after = corrispettivo_service.get_daily_summary(2026, 7)
        day_10 = next(d for d in after.days if d.date == date(2026, 7, 10))
        assert day_10.sales_breakdown.ricevute_imputazione.total_with_tax == Decimal("122.00")
        assert after.month_totals.total_with_tax == Decimal("122.00")

    def test_update_emission_date_moves_totals(
        self, db_session, ricevuta_service, corrispettivo_service, tax, company_info
    ):
        order, _ = seed_paid_order(
            db_session,
            tax,
            reference="XMOD-UPDATE",
            order_date=datetime(2026, 7, 4, 10, 0, 0),
        )
        created = ricevuta_service.create_ricevuta(
            RicevutaCreateSchema(id_order=order.id_order, data_emissione="2026-07-12"),
            user_id=1,
        )

        before = corrispettivo_service.get_daily_summary(2026, 7)
        day_12_before = next(d for d in before.days if d.date == date(2026, 7, 12))
        assert day_12_before.sales.total_with_tax == Decimal("122.00")

        ricevuta_service.update_ricevuta(
            created.id_ricevuta,
            RicevutaUpdateSchema(data_emissione="2026-07-18"),
            user_id=1,
        )

        after = corrispettivo_service.get_daily_summary(2026, 7)
        day_18 = next((d for d in after.days if d.date == date(2026, 7, 18)), None)
        day_12_after = next((d for d in after.days if d.date == date(2026, 7, 12)), None)

        assert day_18 is not None
        assert day_18.sales.total_with_tax == Decimal("122.00")
        assert day_12_after is None or day_12_after.sales.total_with_tax == Decimal("0")

    def test_delete_ricevuta_restores_base_sales(
        self, db_session, ricevuta_service, corrispettivo_service, tax, company_info
    ):
        order, _ = seed_paid_order(
            db_session,
            tax,
            reference="XMOD-DELETE",
            order_date=datetime(2026, 7, 6, 10, 0, 0),
        )
        created = ricevuta_service.create_ricevuta(
            RicevutaCreateSchema(id_order=order.id_order, data_emissione="2026-07-15"),
            user_id=1,
        )

        with_ricevuta = corrispettivo_service.get_daily_summary(2026, 7)
        day_15 = next(d for d in with_ricevuta.days if d.date == date(2026, 7, 15))
        assert day_15.sales_breakdown.ricevute_imputazione.total_with_tax == Decimal("122.00")

        ricevuta_service.delete_ricevuta(created.id_ricevuta, user_id=1)

        assert db_session.query(Ricevuta).count() == 0

        after_delete = corrispettivo_service.get_daily_summary(2026, 7)
        day_6 = next(d for d in after_delete.days if d.date == date(2026, 7, 6))
        assert day_6.sales.total_with_tax == Decimal("122.00")
        assert after_delete.month_totals.total_with_tax == Decimal("122.00")

    def test_same_day_ricevuta_stays_in_base(
        self, db_session, ricevuta_service, corrispettivo_service, tax, company_info
    ):
        order, _ = seed_paid_order(
            db_session,
            tax,
            reference="XMOD-SAME",
            order_date=datetime(2026, 7, 7, 10, 0, 0),
            payment_date=date(2026, 7, 7),
        )
        ricevuta_service.create_ricevuta(
            RicevutaCreateSchema(id_order=order.id_order, data_emissione="2026-07-07"),
            user_id=1,
        )

        summary = corrispettivo_service.get_daily_summary(2026, 7)
        day_7 = next(d for d in summary.days if d.date == date(2026, 7, 7))

        assert day_7.sales_breakdown.base.total_with_tax == Decimal("122.00")
        assert day_7.sales_breakdown.ricevute_decurtazione.total_with_tax == Decimal("0")
        assert day_7.sales_breakdown.ricevute_imputazione.total_with_tax == Decimal("0")
