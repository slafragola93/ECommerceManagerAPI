"""Test filtri lista GET documenti fiscali (paese consegna, range date)."""
from datetime import datetime
from decimal import Decimal

import pytest

from src.models.fiscal_document import FiscalDocument
from src.repository.fiscal_document_repository import FiscalDocumentRepository
from src.schemas.fiscal_document_schema import FiscalDocumentListFiltersSchema
from tests.helpers.fiscal_test_helpers import seed_country, seed_paid_order, seed_tax


@pytest.fixture
def fiscal_repo(db_session):
    return FiscalDocumentRepository(db_session)


def _seed_invoice(
    db_session,
    order,
    *,
    emission_date: datetime,
    status: str = "issued",
) -> FiscalDocument:
    invoice = FiscalDocument(
        document_type="invoice",
        id_order=order.id_order,
        status=status,
        is_electronic=True,
        date_add=emission_date,
        total_price_net=Decimal("100.00"),
        total_price_with_tax=Decimal("122.00"),
    )
    db_session.add(invoice)
    db_session.commit()
    db_session.refresh(invoice)
    return invoice


class TestFiscalDocumentListFiltersRepository:
    def test_filter_by_delivery_country_iso(self, db_session, fiscal_repo):
        tax = seed_tax(db_session)
        order_it, _ = seed_paid_order(
            db_session,
            tax,
            reference="ord-it",
            order_date=datetime(2026, 1, 10),
            country_iso="IT",
        )
        order_fr, _ = seed_paid_order(
            db_session,
            tax,
            reference="ord-fr",
            order_date=datetime(2026, 1, 11),
            country_iso="FR",
        )
        inv_it = _seed_invoice(db_session, order_it, emission_date=datetime(2026, 1, 15))
        _seed_invoice(db_session, order_fr, emission_date=datetime(2026, 1, 16))

        rows = fiscal_repo.get_fiscal_documents(
            document_type="invoice",
            delivery_country_iso="IT",
        )
        assert len(rows) == 1
        assert rows[0].id_fiscal_document == inv_it.id_fiscal_document

        total = fiscal_repo.count_fiscal_documents(
            document_type="invoice",
            delivery_country_iso="IT",
        )
        assert total == 1

    def test_filter_by_date_range(self, db_session, fiscal_repo):
        tax = seed_tax(db_session)
        order_jan, _ = seed_paid_order(
            db_session,
            tax,
            reference="ord-jan",
            order_date=datetime(2026, 1, 5),
        )
        order_feb, _ = seed_paid_order(
            db_session,
            tax,
            reference="ord-feb",
            order_date=datetime(2026, 2, 5),
        )
        inv_jan = _seed_invoice(db_session, order_jan, emission_date=datetime(2026, 1, 20, 10, 0))
        _seed_invoice(db_session, order_feb, emission_date=datetime(2026, 2, 10, 10, 0))

        date_from = datetime(2026, 1, 1)
        date_to = datetime(2026, 1, 31, 23, 59, 59, 999999)

        rows = fiscal_repo.get_fiscal_documents(
            document_type="invoice",
            date_add_from=date_from,
            date_add_to=date_to,
        )
        assert len(rows) == 1
        assert rows[0].id_fiscal_document == inv_jan.id_fiscal_document

    def test_combined_country_and_date_filters(self, db_session, fiscal_repo):
        tax = seed_tax(db_session)
        order_it_jan, _ = seed_paid_order(
            db_session,
            tax,
            reference="it-jan",
            order_date=datetime(2026, 1, 5),
            country_iso="IT",
        )
        order_it_feb, _ = seed_paid_order(
            db_session,
            tax,
            reference="it-feb",
            order_date=datetime(2026, 2, 5),
            country_iso="IT",
        )
        order_fr_jan, _ = seed_paid_order(
            db_session,
            tax,
            reference="fr-jan",
            order_date=datetime(2026, 1, 6),
            country_iso="FR",
        )
        target = _seed_invoice(db_session, order_it_jan, emission_date=datetime(2026, 1, 12))
        _seed_invoice(db_session, order_it_feb, emission_date=datetime(2026, 2, 12))
        _seed_invoice(db_session, order_fr_jan, emission_date=datetime(2026, 1, 13))

        rows = fiscal_repo.get_fiscal_documents(
            document_type="invoice",
            delivery_country_iso="IT",
            date_add_from=datetime(2026, 1, 1),
            date_add_to=datetime(2026, 1, 31, 23, 59, 59, 999999),
        )
        assert len(rows) == 1
        assert rows[0].id_fiscal_document == target.id_fiscal_document


class TestFiscalDocumentListFiltersSchema:
    def test_normalizes_delivery_country_iso(self):
        filters = FiscalDocumentListFiltersSchema(delivery_country_iso="de")
        assert filters.delivery_country_iso == "DE"

    def test_rejects_invalid_date_range(self):
        with pytest.raises(ValueError, match="date_add_to"):
            FiscalDocumentListFiltersSchema(
                date_add_from=datetime(2026, 2, 1).date(),
                date_add_to=datetime(2026, 1, 1).date(),
            )
